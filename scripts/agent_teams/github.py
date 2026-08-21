"""GitHub CLI invocation, pagination, and error classification.

Raw GitHub shapes do not escape this module. Everything above it works in
normalised dictionaries, which is what lets the board layer be tested against
a fake ``gh`` with no network.
"""

from __future__ import annotations

from .errors import AgentTeamsError
from .config import RecoveryConfig

import json
import shutil
import subprocess
import time
from typing import Any, Callable, Iterable, Sequence


class GitHubError(AgentTeamsError):
    """A GitHub CLI invocation failed."""

    def __init__(self, message: str, *, kind: str = "unknown", command: str = ""):
        super().__init__(message)
        self.kind = kind
        self.command = command


class BoardTruncated(GitHubError):
    """The board is larger than this adapter agreed to read in one pass.

    Raised instead of returning a short list. A silently truncated board makes
    dispatch skip real work while reporting success, which is the worst
    failure this adapter can have.
    """


#: stderr fragments -> a classification a Producer skill can act on.
_ERROR_SIGNATURES: tuple[tuple[str, str, str], ...] = (
    (
        "authentication",
        "auth",
        "GitHub authentication is missing or expired; run `gh auth login`",
    ),
    (
        "not logged into",
        "auth",
        "GitHub authentication is missing or expired; run `gh auth login`",
    ),
    (
        "requires the",
        "scope",
        "the token is missing a required scope; re-run `gh auth refresh -s project`",
    ),
    (
        "missing required scopes",
        "scope",
        "the token is missing a required scope; re-run `gh auth refresh -s project`",
    ),
    ("could not resolve to a projectv2", "not_found", "the Project was not found"),
    ("could not resolve to a repository", "not_found", "the repository was not found"),
    ("not found", "not_found", "the requested GitHub resource was not found"),
    ("resource not accessible", "permission", "the token cannot access this resource"),
    ("rate limit", "rate_limit", "the GitHub API rate limit is exhausted"),
    ("failed to connect", "network", "GitHub could not be reached"),
    ("could not resolve host", "network", "GitHub could not be reached"),
    ("connection refused", "network", "GitHub could not be reached"),
    ("connection reset", "network", "the GitHub connection was interrupted"),
    ("operation timed out", "network", "the GitHub connection timed out"),
    ("timed out", "network", "the GitHub connection timed out"),
    ("temporary failure", "network", "GitHub could not be reached temporarily"),
    ("503 service unavailable", "server", "GitHub is temporarily unavailable"),
    ("502 bad gateway", "server", "GitHub is temporarily unavailable"),
    ("504 gateway timeout", "server", "GitHub is temporarily unavailable"),
    ("internal server error", "server", "GitHub returned a transient server error"),
)

_RETRYABLE_ERROR_KINDS = frozenset(("network", "rate_limit", "server"))

# Only unambiguously read-only commands may be replayed below the workflow
# layer. A failed Issue creation may have succeeded remotely before the client
# lost its response; blindly retrying it would create a duplicate.
_SAFE_READ_COMMANDS = frozenset({
    ("auth", "status"),
    ("issue", "list"),
    ("issue", "view"),
    ("pr", "checks"),
    ("pr", "list"),
    ("pr", "status"),
    ("pr", "view"),
    ("project", "field-list"),
    ("project", "item-list"),
    ("project", "view"),
    ("repo", "view"),
    ("run", "list"),
    ("run", "view"),
})


def classify(stderr: str) -> tuple[str, str]:
    """Map raw stderr onto a (kind, human explanation) pair."""
    haystack = (stderr or "").casefold()
    for needle, kind, explanation in _ERROR_SIGNATURES:
        if needle in haystack:
            return kind, explanation
    return "unknown", ""


def _graphql_is_query(args: Sequence[str]) -> bool:
    """``gh api graphql`` is a read iff every document it sends is a query."""
    documents = []
    for index, argument in enumerate(args):
        if argument in {"-f", "--raw-field"} and index + 1 < len(args):
            key, _, value = args[index + 1].partition("=")
            if key == "query":
                documents.append(value)
        elif argument.startswith("--raw-field=query=") or argument.startswith("-fquery="):
            documents.append(argument.split("query=", 1)[1])
    return bool(documents) and all(
        document.lstrip().startswith(("query", "{")) for document in documents
    )


def _is_safe_read(args: Sequence[str]) -> bool:
    if not args:
        return False
    if list(args[:2]) == ["api", "graphql"]:
        return (
            not any(a in {"-X", "--method"} for a in args[2:])
            and _graphql_is_query(args)
        )
    if args[0] == "api":
        write_flags = {
            "-X", "--method", "-f", "-F", "--field", "--raw-field", "--input"
        }
        return not any(argument in write_flags for argument in args[1:])
    return tuple(args[:2]) in _SAFE_READ_COMMANDS


class Gh:
    """A small injectable wrapper around the GitHub CLI."""

    executable = "gh"

    def __init__(
        self,
        recovery: RecoveryConfig | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.recovery = recovery or RecoveryConfig()
        self._sleep = sleep
        #: Count of commands issued that may have changed GitHub state. Board
        #: keys its per-process read cache on it: a read is reused until
        #: something this process did could have invalidated it.
        self.mutations = 0

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def run(self, args: Iterable[str]) -> str:
        arguments = list(args)
        command = [self.executable, *arguments]
        safe_read = _is_safe_read(arguments)
        if not safe_read:
            self.mutations += 1
        attempt = 0
        while True:
            attempt += 1
            outcome = self._run_once(command, attempt)
            if isinstance(outcome, str):
                return outcome
            if (
                not safe_read
                or outcome.kind not in _RETRYABLE_ERROR_KINDS
                or attempt > self.recovery.max_retries
            ):
                raise outcome
            self._sleep(self.recovery.retry_delay_seconds(attempt))

    def _run_once(self, command: list[str], attempt: int) -> str | GitHubError:
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except FileNotFoundError:
            return GitHubError(
                "gh is not installed or is not on PATH",
                kind="missing",
                command=" ".join(command),
            )
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip() or (completed.stdout or "").strip()
            kind, explanation = classify(detail)
            attempt_note = f" after {attempt} attempts" if attempt > 1 else ""
            message = f"{' '.join(command)} failed{attempt_note}: {detail}"
            if explanation:
                message += f"\n  -> {explanation}"
            return GitHubError(message, kind=kind, command=" ".join(command))
        return (completed.stdout or "").strip()

    def json(self, args: Iterable[str]) -> Any:
        output = self.run(args)
        if not output:
            return {}
        try:
            return json.loads(output)
        except json.JSONDecodeError as exc:
            raise GitHubError(
                f"gh returned invalid JSON: {output[:200]}", kind="protocol"
            ) from exc


def fetch_all_items(
    fetch: Callable[[int], Sequence[Any]],
    *,
    page_limit: int,
    max_items: int,
    what: str = "Project items",
) -> list[Any]:
    """Read every item, or fail loudly rather than return a partial board.

    ``gh project item-list`` takes a ``--limit`` and paginates internally up to
    it. There is no cursor to follow, so the only way to know a response was
    truncated is that it came back exactly saturated. This escalates the limit
    until a response comes back short -- proof it is complete -- and raises
    ``BoardTruncated`` if the board outgrows ``max_items``.

    The extra request when a board's size lands exactly on a boundary is the
    price of never silently dropping a Card from dispatch.
    """
    limit = max(1, page_limit)
    while True:
        items = list(fetch(limit))
        if len(items) < limit:
            return items
        if limit >= max_items:
            raise BoardTruncated(
                f"the Project returned {len(items)} {what} at the {max_items} "
                f"item ceiling, so the board may extend past what was read. "
                f"Refusing to report a possibly partial board. Raise max_items "
                f"or narrow the Project.",
                kind="truncated",
            )
        limit = min(limit * 2, max_items)
