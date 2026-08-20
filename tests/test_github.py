"""GitHub transport retry and backoff safety tests."""

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts"))

from agent_teams.config import RecoveryConfig  # noqa: E402
from agent_teams.github import Gh, GitHubError, classify  # noqa: E402


def completed(returncode, *, stdout="", stderr=""):
    return subprocess.CompletedProcess(
        args=["gh"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class ErrorClassificationTests(unittest.TestCase):
    def test_transient_network_and_server_errors_are_named(self):
        self.assertEqual(classify("failed to connect to github.com")[0], "network")
        self.assertEqual(classify("503 Service Unavailable")[0], "server")


class RetryTests(unittest.TestCase):
    def policy(self, **overrides):
        values = {
            "max_retries": 2,
            "initial_backoff_seconds": 1,
            "backoff_multiplier": 2,
            "max_backoff_seconds": 1.5,
        }
        values.update(overrides)
        return RecoveryConfig(**values)

    @patch("agent_teams.github.subprocess.run")
    def test_safe_read_retries_transient_failures_with_bounded_backoff(self, run):
        run.side_effect = [
            completed(1, stderr="failed to connect to github.com"),
            completed(1, stderr="503 Service Unavailable"),
            completed(0, stdout='{"id":"PROJECT"}'),
        ]
        delays = []
        gh = Gh(recovery=self.policy(), sleep=delays.append)

        self.assertEqual(gh.run(["project", "view", "1"]), '{"id":"PROJECT"}')
        self.assertEqual(run.call_count, 3)
        self.assertEqual(delays, [1.0, 1.5])

    @patch("agent_teams.github.subprocess.run")
    def test_mutation_is_never_blindly_retried(self, run):
        run.return_value = completed(1, stderr="failed to connect to github.com")
        delays = []
        gh = Gh(recovery=self.policy(), sleep=delays.append)

        with self.assertRaises(GitHubError):
            gh.run(["issue", "create", "--title", "Do not duplicate"])
        self.assertEqual(run.call_count, 1)
        self.assertEqual(delays, [])

    @patch("agent_teams.github.subprocess.run")
    def test_non_transient_read_failure_stops_immediately(self, run):
        run.return_value = completed(1, stderr="authentication required")
        delays = []
        gh = Gh(recovery=self.policy(), sleep=delays.append)

        with self.assertRaises(GitHubError) as caught:
            gh.run(["project", "view", "1"])
        self.assertEqual(caught.exception.kind, "auth")
        self.assertEqual(run.call_count, 1)
        self.assertEqual(delays, [])

    @patch("agent_teams.github.subprocess.run")
    def test_exhausted_retries_surface_the_attempt_count(self, run):
        run.return_value = completed(1, stderr="connection reset by peer")
        gh = Gh(recovery=self.policy(max_retries=1), sleep=lambda _: None)

        with self.assertRaisesRegex(GitHubError, "after 2 attempts"):
            gh.run(["issue", "view", "12"])
        self.assertEqual(run.call_count, 2)


if __name__ == "__main__":
    unittest.main()
