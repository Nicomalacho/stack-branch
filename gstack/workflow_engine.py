"""Workflow engine for gstack sync, continue, and abort operations.

Handles the complex multi-step logic for rebasing stacked branches.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import typer

from gstack import gh_ops, git_ops, stack_manager
from gstack.exceptions import (
    DirtyWorkdirError,
    GhNotAuthenticatedError,
    NoPendingOperationError,
    PendingOperationError,
)
from gstack.models import SyncState


@dataclass
class SyncResult:
    """Result of a sync operation."""

    success: bool
    rebased_branches: list[str] = field(default_factory=list)
    conflict_branch: Optional[str] = None
    message: str = ""


def get_merged_branches(repo_root: Path) -> list[str]:
    """Get list of tracked branches that have been merged.

    Args:
        repo_root: Repository root directory.

    Returns:
        List of branch names that have merged PRs.
    """
    config = stack_manager.load_config(repo_root)
    merged = []

    for branch in config.branches:
        if gh_ops.is_pr_merged(branch):
            merged.append(branch)

    return merged


def run_sync(repo_root: Path) -> SyncResult:
    """Run the sync workflow to rebase the current stack.

    Algorithm:
    1. Validate: workdir clean, no pending state
    2. Build queue: current branch + descendants in topological order
    3. Save state
    4. For each branch:
       a. Checkout branch
       b. Rebase onto parent
       c. On conflict: preserve state, return
       d. On success: continue
    5. Cleanup: delete state, return to original branch

    Args:
        repo_root: Repository root directory.

    Returns:
        SyncResult with success status and rebased branches.

    Raises:
        DirtyWorkdirError: If working directory has uncommitted changes.
        PendingOperationError: If there's already a pending operation.
    """
    # Validate workdir is clean
    if not git_ops.is_workdir_clean():
        raise DirtyWorkdirError()

    # Check for pending state
    if stack_manager.has_pending_state(repo_root):
        raise PendingOperationError("sync")

    config = stack_manager.load_config(repo_root)
    current_branch = git_ops.get_current_branch()

    # If on trunk or not tracking any branches, nothing to do
    if current_branch == config.trunk or not config.branches:
        return SyncResult(success=True, message="Nothing to sync.")

    # Build the queue of branches to rebase
    # Get the full stack: ancestors + current branch + descendants
    branches_to_sync = set()

    if current_branch in config.branches:
        # Get full stack from trunk to current branch
        stack = config.get_stack(current_branch)
        # Add all branches in the stack (excluding trunk)
        for branch in stack:
            if branch != config.trunk:
                branches_to_sync.add(branch)
                # Also add descendants of each branch in the stack
                descendants = config.get_descendants(branch)
                branches_to_sync.update(descendants)

    if not branches_to_sync:
        return SyncResult(success=True, message="Nothing to sync.")

    branches_to_sync = list(branches_to_sync)

    # Sort topologically (parents before children)
    branches_to_sync = config.topological_sort(branches_to_sync)

    # Save state
    state = SyncState(
        active_command="sync",
        todo_queue=branches_to_sync,
        current_index=0,
        original_head=current_branch,
    )
    stack_manager.save_state(state, repo_root)

    # Execute sync
    return _execute_sync(repo_root, state, config)


def _execute_sync(repo_root: Path, state: SyncState, config=None) -> SyncResult:
    """Execute the sync loop starting from the current state.

    Args:
        repo_root: Repository root directory.
        state: Current sync state.
        config: StackConfig (loaded if not provided).

    Returns:
        SyncResult with status and rebased branches.
    """
    if config is None:
        config = stack_manager.load_config(repo_root)

    rebased_branches = []

    while not state.is_complete:
        branch = state.current_branch
        if branch is None:
            break

        branch_info = config.branches.get(branch)
        if branch_info is None:
            # Branch not in config, skip
            state.current_index += 1
            stack_manager.save_state(state, repo_root)
            continue

        parent = branch_info.parent

        # Checkout the branch
        git_ops.checkout_branch(branch)

        # Squash commits before rebasing to reduce conflicts
        git_ops.squash_commits(parent)

        # Rebase onto parent
        result = git_ops.rebase(parent, check=False)

        if result.returncode != 0:
            # Conflict detected
            stack_manager.save_state(state, repo_root)
            return SyncResult(
                success=False,
                rebased_branches=rebased_branches,
                conflict_branch=branch,
                message=f"Conflict while rebasing '{branch}'. "
                f"Resolve conflicts, stage files, then run 'gstack continue'.",
            )

        rebased_branches.append(branch)
        state.current_index += 1
        stack_manager.save_state(state, repo_root)

    # Success - cleanup
    stack_manager.clear_state(repo_root)

    # Return to original branch
    git_ops.checkout_branch(state.original_head)

    return SyncResult(
        success=True,
        rebased_branches=rebased_branches,
        message=f"Successfully rebased {len(rebased_branches)} branch(es).",
    )


def run_continue(repo_root: Path) -> SyncResult:
    """Continue a sync operation after resolving conflicts.

    Args:
        repo_root: Repository root directory.

    Returns:
        SyncResult with status.

    Raises:
        NoPendingOperationError: If no pending operation exists.
    """
    state = stack_manager.load_state(repo_root)
    if state is None:
        raise NoPendingOperationError()

    config = stack_manager.load_config(repo_root)

    # Continue the rebase
    if git_ops.is_rebase_in_progress():
        result = git_ops.run_git("rebase", "--continue", check=False)
        if result.returncode != 0:
            # Still has conflicts
            return SyncResult(
                success=False,
                conflict_branch=state.current_branch,
                message="Conflicts remain. Resolve them and run 'gstack continue' again.",
            )

    # Mark current branch as done and continue
    rebased_branches = [state.current_branch] if state.current_branch else []
    state.current_index += 1
    stack_manager.save_state(state, repo_root)

    # Continue with the rest
    result = _execute_sync(repo_root, state, config)
    result.rebased_branches = rebased_branches + result.rebased_branches

    # Auto-submit after successful sync
    if result.success:
        try:
            submit_result = run_submit(repo_root)
            if submit_result.success:
                result.message = f"{result.message} Auto-submitted changes."
        except Exception:
            # Submit failed - don't fail the continue operation
            pass

    return result


def run_abort(repo_root: Path) -> None:
    """Abort the current sync operation.

    Args:
        repo_root: Repository root directory.

    Raises:
        NoPendingOperationError: If no pending operation exists.
    """
    state = stack_manager.load_state(repo_root)
    if state is None:
        raise NoPendingOperationError()

    # Abort rebase if in progress
    if git_ops.is_rebase_in_progress():
        git_ops.rebase_abort()

    # Return to original branch
    try:
        git_ops.checkout_branch(state.original_head)
    except Exception:
        # Best effort - might fail if branch was modified
        pass

    # Clear state
    stack_manager.clear_state(repo_root)


@dataclass
class SubmitResult:
    """Result of a submit operation."""

    success: bool
    pushed_branches: list[str] = field(default_factory=list)
    created_prs: list[str] = field(default_factory=list)
    updated_prs: list[str] = field(default_factory=list)
    message: str = ""


def run_submit(repo_root: Path) -> SubmitResult:
    """Run the submit workflow to push branches and manage PRs.

    Algorithm:
    1. Validate: workdir clean
    2. Check gh authentication
    3. Sync (rebase) all branches first
    4. Get full stack from current branch
    5. For each branch (bottom-up):
       a. Push with force-with-lease (+ -u if first push)
       b. Check if PR exists
       c. Create PR or update base as needed
       d. Store pr_url in config
    6. Save config

    Args:
        repo_root: Repository root directory.

    Returns:
        SubmitResult with success status and affected branches.

    Raises:
        DirtyWorkdirError: If working directory has uncommitted changes.
        GhNotAuthenticatedError: If GitHub CLI is not authenticated.
    """
    # Validate workdir is clean
    if not git_ops.is_workdir_clean():
        raise DirtyWorkdirError()

    # Check gh authentication
    if not gh_ops.is_gh_authenticated():
        raise GhNotAuthenticatedError()

    # Sync (rebase) all branches first to ensure they're up to date
    sync_result = run_sync(repo_root)
    if not sync_result.success:
        return SubmitResult(
            success=False,
            message=f"Sync failed: {sync_result.message}",
        )

    config = stack_manager.load_config(repo_root)
    current_branch = git_ops.get_current_branch()

    # If on trunk or not tracking any branches, nothing to do
    if current_branch == config.trunk or not config.branches:
        return SubmitResult(success=True, message="Nothing to submit.")

    # Build the list of branches to submit
    # Get the full stack from current branch
    branches_to_submit = set()

    if current_branch in config.branches:
        # Get full stack from trunk to current branch
        stack = config.get_stack(current_branch)
        # Add all branches in the stack (excluding trunk)
        for branch in stack:
            if branch != config.trunk:
                branches_to_submit.add(branch)
                # Also add descendants of each branch in the stack
                descendants = config.get_descendants(branch)
                branches_to_submit.update(descendants)

    if not branches_to_submit:
        return SubmitResult(success=True, message="Nothing to submit.")

    # Sort topologically (parents before children)
    branches_to_submit = config.topological_sort(list(branches_to_submit))

    pushed_branches = []
    created_prs = []
    updated_prs = []

    for branch in branches_to_submit:
        branch_info = config.branches.get(branch)
        if branch_info is None:
            continue

        parent = branch_info.parent

        # Push the branch
        try:
            # Check if upstream is set
            has_upstream = _branch_has_upstream(branch)
            git_ops.push("origin", branch, force_with_lease=True, set_upstream=not has_upstream)
            pushed_branches.append(branch)
        except Exception as e:
            return SubmitResult(
                success=False,
                pushed_branches=pushed_branches,
                created_prs=created_prs,
                updated_prs=updated_prs,
                message=f"Failed to push '{branch}': {e}",
            )

        # Check/create/update PR
        pr_info = gh_ops.get_pr_info(branch)

        if pr_info is None:
            # Create new PR with a description
            try:
                body = f"Part of stack based on `{parent}`.\n\nCreated with [gstack](https://github.com/nicomalacho/stack-branch)."
                result = gh_ops.create_pr(head=branch, base=parent, body=body)
                created_prs.append(branch)
                # Update config with PR URL
                config.branches[branch].pr_url = result.url
            except Exception as e:
                # PR creation failed - log but continue with other branches
                typer.echo(f"  Warning: Failed to create PR for '{branch}': {e}", err=True)
                pass
        else:
            # PR exists - check if base needs updating
            if pr_info.base != parent:
                try:
                    gh_ops.update_pr_base(branch, parent)
                    updated_prs.append(branch)
                except Exception:
                    # Base update failed - not critical
                    pass

            # Update config with PR URL
            config.branches[branch].pr_url = pr_info.url

    # Save config with PR URLs
    stack_manager.save_config(config, repo_root)

    # Post mermaid diagram to all PRs in the stack
    _post_stack_diagrams(config, branches_to_submit, current_branch)

    return SubmitResult(
        success=True,
        pushed_branches=pushed_branches,
        created_prs=created_prs,
        updated_prs=updated_prs,
        message=f"Pushed {len(pushed_branches)} branch(es), "
        f"created {len(created_prs)} PR(s), "
        f"updated {len(updated_prs)} PR(s).",
    )


def _post_stack_diagrams(config, branches: list[str], current_branch: str) -> None:
    """Post mermaid stack diagrams to all PRs in the given branches.

    Args:
        config: StackConfig with branch info.
        branches: List of branches to post diagrams to.
        current_branch: Currently checked out branch.
    """
    # Only include branches that are in the submit list
    relevant_branches = {name: info for name, info in config.branches.items() if name in branches}

    if not relevant_branches:
        return

    # Generate the diagram
    diagram = gh_ops.generate_stack_mermaid(
        relevant_branches,
        config.trunk,
        current_branch,
    )

    # Post to each PR
    for branch in branches:
        try:
            gh_ops.add_or_update_stack_comment(branch, diagram)
        except Exception:
            # Non-critical - don't fail submit if diagram posting fails
            pass


def _branch_has_upstream(branch: str) -> bool:
    """Check if a branch has an upstream tracking branch configured."""
    result = git_ops.run_git("config", "--get", f"branch.{branch}.remote", check=False)
    return result.returncode == 0


@dataclass
class PushResult:
    """Result of a push operation for a single branch."""

    success: bool
    branch: str
    pr_created: bool = False
    pr_updated: bool = False
    pr_url: Optional[str] = None
    message: str = ""


def run_push(repo_root: Path) -> PushResult:
    """Push the current branch and create/update its PR.

    This is a lightweight version of submit that only handles the current branch,
    useful for quick iterations on a single PR.

    Args:
        repo_root: Repository root directory.

    Returns:
        PushResult with status.

    Raises:
        DirtyWorkdirError: If working directory has uncommitted changes.
        GhNotAuthenticatedError: If GitHub CLI is not authenticated.
    """
    # Validate workdir is clean
    if not git_ops.is_workdir_clean():
        raise DirtyWorkdirError()

    # Check gh authentication
    if not gh_ops.is_gh_authenticated():
        raise GhNotAuthenticatedError()

    config = stack_manager.load_config(repo_root)
    current_branch = git_ops.get_current_branch()

    # If on trunk or not a tracked branch, nothing to do
    if current_branch == config.trunk:
        return PushResult(
            success=True,
            branch=current_branch,
            message="Cannot push trunk branch.",
        )

    if current_branch not in config.branches:
        return PushResult(
            success=False,
            branch=current_branch,
            message=f"Branch '{current_branch}' is not tracked by gstack. "
            f"Use 'gstack create' to create tracked branches.",
        )

    branch_info = config.branches[current_branch]
    parent = branch_info.parent

    # Push the branch
    try:
        has_upstream = _branch_has_upstream(current_branch)
        git_ops.push("origin", current_branch, force_with_lease=True, set_upstream=not has_upstream)
    except Exception as e:
        return PushResult(
            success=False,
            branch=current_branch,
            message=f"Failed to push: {e}",
        )

    # Check/create/update PR
    pr_info = gh_ops.get_pr_info(current_branch)
    pr_created = False
    pr_updated = False
    pr_url = None

    if pr_info is None:
        # Create new PR with a description
        try:
            body = f"Part of stack based on `{parent}`.\n\nCreated with [gstack](https://github.com/nicomalacho/stack-branch)."
            result = gh_ops.create_pr(head=current_branch, base=parent, body=body)
            pr_created = True
            pr_url = result.url
            config.branches[current_branch].pr_url = result.url
        except Exception as e:
            return PushResult(
                success=True,  # Push succeeded
                branch=current_branch,
                pr_created=False,
                message=f"Pushed successfully, but failed to create PR: {e}",
            )
    else:
        pr_url = pr_info.url
        config.branches[current_branch].pr_url = pr_info.url

        # Check if base needs updating
        if pr_info.base != parent:
            try:
                gh_ops.update_pr_base(current_branch, parent)
                pr_updated = True
            except Exception:
                pass  # Not critical

    # Save config with PR URL
    stack_manager.save_config(config, repo_root)

    # Post mermaid diagram to the PR
    try:
        # Get full stack for the diagram
        stack = config.get_stack(current_branch)
        relevant_branches = {
            name: info
            for name, info in config.branches.items()
            if name in stack and name != config.trunk
        }
        if relevant_branches:
            diagram = gh_ops.generate_stack_mermaid(
                relevant_branches,
                config.trunk,
                current_branch,
            )
            gh_ops.add_or_update_stack_comment(current_branch, diagram)
    except Exception:
        pass  # Non-critical

    if pr_created:
        message = f"Pushed and created PR: {pr_url}"
    elif pr_updated:
        message = f"Pushed and updated PR base: {pr_url}"
    else:
        message = f"Pushed: {pr_url}"

    return PushResult(
        success=True,
        branch=current_branch,
        pr_created=pr_created,
        pr_updated=pr_updated,
        pr_url=pr_url,
        message=message,
    )


@dataclass
class MoveResult:
    """Result of a move operation."""

    success: bool
    branch: str
    old_parent: str
    new_parent: str
    pr_updated: bool = False
    message: str = ""


def run_move(repo_root: Path, branch: str, new_parent: str) -> MoveResult:
    """Move a branch to a new parent.

    Algorithm:
    1. Validate: branch exists, new_parent exists
    2. Update config: change parent, fix children lists
    3. Checkout and rebase onto new parent
    4. Update PR base on GitHub (if PR exists)
    5. Return to original branch

    Args:
        repo_root: Repository root directory.
        branch: Branch to move.
        new_parent: New parent branch.

    Returns:
        MoveResult with status.
    """
    config = stack_manager.load_config(repo_root)
    current_branch = git_ops.get_current_branch()

    # Validation: branch must be tracked
    if branch not in config.branches:
        return MoveResult(
            success=False,
            branch=branch,
            old_parent="",
            new_parent=new_parent,
            message=f"Branch '{branch}' is not tracked by gstack.",
        )

    # Validation: new_parent must exist (either as tracked branch or trunk)
    if new_parent != config.trunk and not git_ops.branch_exists(new_parent):
        return MoveResult(
            success=False,
            branch=branch,
            old_parent="",
            new_parent=new_parent,
            message=f"Branch '{new_parent}' does not exist.",
        )

    old_parent = config.branches[branch].parent

    # Check if already on the target parent
    if old_parent == new_parent:
        return MoveResult(
            success=True,
            branch=branch,
            old_parent=old_parent,
            new_parent=new_parent,
            message=f"Branch '{branch}' is already on '{new_parent}'.",
        )

    # Update config
    stack_manager.reparent_branch(branch, new_parent, repo_root)

    # Checkout and rebase
    git_ops.checkout_branch(branch)
    result = git_ops.rebase(new_parent, check=False)

    if result.returncode != 0:
        # Conflict - save state for continue
        state = SyncState(
            active_command="move",
            todo_queue=[branch],
            current_index=0,
            original_head=current_branch,
        )
        stack_manager.save_state(state, repo_root)
        return MoveResult(
            success=False,
            branch=branch,
            old_parent=old_parent,
            new_parent=new_parent,
            message=f"Conflict while rebasing '{branch}'. "
            f"Resolve conflicts, then run 'gstack continue'.",
        )

    # Update PR base on GitHub
    pr_updated = False
    try:
        pr_info = gh_ops.get_pr_info(branch)
        if pr_info and pr_info.base != new_parent:
            gh_ops.update_pr_base(branch, new_parent)
            pr_updated = True
    except Exception:
        pass  # PR update is not critical

    # Return to original branch
    git_ops.checkout_branch(current_branch)

    return MoveResult(
        success=True,
        branch=branch,
        old_parent=old_parent,
        new_parent=new_parent,
        pr_updated=pr_updated,
        message=f"Moved '{branch}' from '{old_parent}' to '{new_parent}'.",
    )
