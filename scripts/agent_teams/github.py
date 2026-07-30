"""GitHub CLI invocation, pagination, and error classification.

Raw GitHub shapes do not escape this module. Everything above it works in
normalised dictionaries, which is what lets the board layer be tested against
a fake ``gh`` with no network.
"""

from __future__ import annotations

from .errors import AgentTeamsError

import json
import shutil
import subprocess
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
)


def classify(stderr: str) -> tuple[str, str]:
    """Map raw stderr onto a (kind, human explanation) pair."""
    haystack = (stderr or "").casefold()
    for needle, kind, explanation in _ERROR_SIGNATURES:
        if needle in haystack:
            return kind, explanation
    return "unknown", ""


class Gh:
    """A small injectable wrapper around the GitHub CLI."""

    executable = "gh"

    def available(self) -> bool:
        return shutil.which(self.executable) is not None

    def run(self, args: Iterable[str]) -> str:
        command = [self.executable, *list(args)]
        try:
            completed = subprocess.run(
                command,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
        except FileNotFoundError as exc:
            raise GitHubError(
                "gh is not installed or is not on PATH",
                kind="missing",
                command=" ".join(command),
            ) from exc
        if completed.returncode != 0:
            detail = (completed.stderr or "").strip() or (completed.stdout or "").strip()
            kind, explanation = classify(detail)
            message = f"{' '.join(command)} failed: {detail}"
            if explanation:
                message += f"\n  -> {explanation}"
            raise GitHubError(message, kind=kind, command=" ".join(command))
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


DEFAULT_PAGE_LIMIT = 100
DEFAULT_MAX_ITEMS = 2000


def fetch_all_items(
    fetch: Callable[[int], Sequence[Any]],
    *,
    page_limit: int = DEFAULT_PAGE_LIMIT,
    max_items: int = DEFAULT_MAX_ITEMS,
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
