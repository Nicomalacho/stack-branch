"""GitHub CLI operations wrapper for gstack.

All gh commands are executed via subprocess, capturing output for error handling.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from typing import Optional

from gstack.exceptions import GhError, GhNotAuthenticatedError


@dataclass
class GhResult:
    """Result of a gh command execution."""

    stdout: str
    stderr: str
    returncode: int


@dataclass
class PrInfo:
    """Information about a pull request."""

    url: str
    base: str
    state: str
    number: int


@dataclass
class PrCreateResult:
    """Result of creating a pull request."""

    url: str
    number: int


def run_gh(*args: str, check: bool = True) -> GhResult:
    """Run a gh command and return the result.

    Args:
        *args: gh command arguments (e.g., "pr", "view").
        check: If True, raise GhError on non-zero exit code.

    Returns:
        GhResult with stdout, stderr, and returncode.

    Raises:
        GhError: If check=True and command fails.
    """
    cmd = ["gh", *args]
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
    )

    gh_result = GhResult(
        stdout=result.stdout,
        stderr=result.stderr,
        returncode=result.returncode,
    )

    if check and result.returncode != 0:
        error_msg = (
            result.stderr.strip() or result.stdout.strip() or f"gh command failed: {' '.join(cmd)}"
        )
        raise GhError(error_msg, returncode=result.returncode, stderr=result.stderr)

    return gh_result


def is_gh_authenticated() -> bool:
    """Check if the GitHub CLI is authenticated.

    Returns:
        True if authenticated, False otherwise.
    """
    result = run_gh("auth", "status", check=False)
    return result.returncode == 0


def require_gh_auth() -> None:
    """Require the GitHub CLI to be authenticated.

    Raises:
        GhNotAuthenticatedError: If not authenticated.
    """
    if not is_gh_authenticated():
        raise GhNotAuthenticatedError()


def get_pr_info(branch: str) -> Optional[PrInfo]:
    """Get information about a pull request for a branch.

    Args:
        branch: Branch name to check for PR.

    Returns:
        PrInfo if PR exists, None otherwise.
    """
    result = run_gh(
        "pr",
        "view",
        branch,
        "--json",
        "url,baseRefName,state,number",
        check=False,
    )

    if result.returncode != 0:
        return None

    try:
        data = json.loads(result.stdout)
        return PrInfo(
            url=data["url"],
            base=data["baseRefName"],
            state=data["state"],
            number=data["number"],
        )
    except (json.JSONDecodeError, KeyError):
        return None


def create_pr(
    head: str,
    base: str,
    title: Optional[str] = None,
    body: Optional[str] = None,
) -> PrCreateResult:
    """Create a new pull request.

    Args:
        head: Head branch name.
        base: Base branch name.
        title: PR title (auto-generated if None).
        body: PR body (empty if None).

    Returns:
        PrCreateResult with URL and number.

    Raises:
        GhError: If PR creation fails.
    """
    # Note: gh pr create does NOT support --json flag
    # It outputs the PR URL directly to stdout
    args = [
        "pr",
        "create",
        "--head",
        head,
        "--base",
        base,
    ]

    if title:
        args.extend(["--title", title])
    else:
        args.append("--fill")

    if body:
        args.extend(["--body", body])

    result = run_gh(*args)

    # Parse URL from stdout (gh pr create outputs URL directly)
    url = result.stdout.strip()

    # Extract PR number from URL (e.g., https://github.com/org/repo/pull/42)
    try:
        number = int(url.split("/")[-1])
    except (ValueError, IndexError):
        number = 0

    return PrCreateResult(
        url=url,
        number=number,
    )


def update_pr_base(branch: str, new_base: str) -> None:
    """Update the base branch of a pull request.

    Args:
        branch: Branch name with the PR.
        new_base: New base branch name.

    Raises:
        GhError: If update fails.
    """
    run_gh("pr", "edit", branch, "--base", new_base)


def is_pr_merged(branch: str) -> bool:
    """Check if a pull request has been merged.

    Args:
        branch: Branch name to check.

    Returns:
        True if PR exists and is merged, False otherwise.
    """
    info = get_pr_info(branch)
    if info is None:
        return False
    return info.state == "MERGED"


STACK_COMMENT_MARKER = "<!-- gstack-diagram -->"


def add_or_update_stack_comment(branch: str, comment_body: str) -> None:
    """Add or update a stack diagram comment on a PR.

    If a comment with the gstack marker exists, it will be updated.
    Otherwise, a new comment will be created.

    Args:
        branch: Branch name with the PR.
        comment_body: The comment body (should include STACK_COMMENT_MARKER).

    Raises:
        GhError: If comment operation fails.
    """
    pr_info = get_pr_info(branch)
    if pr_info is None:
        return

    # Get existing comments to find our marker
    result = run_gh(
        "pr",
        "view",
        branch,
        "--json",
        "comments",
        check=False,
    )

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout)
            comments = data.get("comments", [])

            # Look for existing gstack comment
            for comment in comments:
                if STACK_COMMENT_MARKER in comment.get("body", ""):
                    # Update existing comment
                    comment_id = comment.get("id")
                    if comment_id:
                        # gh doesn't have a direct way to edit PR comments,
                        # so we delete and recreate
                        # Actually, we can use the API directly
                        run_gh(
                            "api",
                            "-X",
                            "PATCH",
                            f"/repos/{{owner}}/{{repo}}/issues/comments/{comment_id}",
                            "-f",
                            f"body={comment_body}",
                            check=False,
                        )
                        return
        except (json.JSONDecodeError, KeyError):
            pass

    # No existing comment found, create new one
    run_gh("pr", "comment", branch, "--body", comment_body, check=False)


def generate_stack_mermaid(
    branches: dict,
    trunk: str,
    current_branch: Optional[str] = None,
) -> str:
    """Generate a mermaid diagram for the stack.

    Args:
        branches: Dict of branch name -> BranchInfo.
        trunk: Name of the trunk branch.
        current_branch: Currently checked out branch (highlighted).

    Returns:
        Mermaid diagram as a string.
    """
    lines = [
        STACK_COMMENT_MARKER,
        "## Stack Overview",
        "",
        "```mermaid",
        "graph TD",
        f"    {trunk}[{trunk}]",
    ]

    # Build the graph
    for name, info in branches.items():
        # Node with PR link if available
        if info.pr_url:
            pr_num = info.pr_url.split("/")[-1]
            # Use quoted label to avoid mermaid parsing issues with brackets
            # Valid: name["name #42"]
            # Invalid: name[name [#42]] - nested brackets break mermaid
            label = f"{name} #{pr_num}"
            lines.append(f'    {name}["{label}"]')
            # Use mermaid click directive for clickable links (not HTML <a> tags)
            lines.append(f'    click {name} href "{info.pr_url}" _blank')
        else:
            lines.append(f"    {name}[{name}]")

        # Edge from parent to this branch
        lines.append(f"    {info.parent} --> {name}")

        # Highlight current branch
        if name == current_branch:
            lines.append(f"    style {name} fill:#90EE90")

    lines.append("```")
    lines.append("")
    lines.append("*Updated by gstack*")

    return "\n".join(lines)
