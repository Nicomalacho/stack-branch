"""CLI entry point for gstack."""

from typing import Optional

import typer

from gstack import git_ops, stack_manager
from gstack.exceptions import (
    DirtyWorkdirError,
    GitError,
    NotAGitRepoError,
    NotInitializedError,
)
from gstack.stack_manager import AlreadyInitializedError

app = typer.Typer(
    name="gstack",
    help="Manage stacked Git branches with automated rebasing and GitHub PR management.",
    no_args_is_help=True,
)


def get_repo_root_or_exit():
    """Get the repository root, or exit with error if not in a git repo."""
    from pathlib import Path

    try:
        return git_ops.get_repo_root()
    except NotAGitRepoError:
        typer.echo("Error: Not a git repository.", err=True)
        raise typer.Exit(1)


@app.command()
def init(
    trunk: Optional[str] = typer.Option(
        None, "--trunk", "-t", help="Trunk branch name (auto-detected if not specified)"
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force reinitialization if already initialized"
    ),
) -> None:
    """Initialize gstack in the current repository."""
    repo_root = get_repo_root_or_exit()

    try:
        config = stack_manager.init_config(repo_root, trunk=trunk, force=force)
        typer.echo(f"Initialized gstack with trunk branch '{config.trunk}'.")
    except AlreadyInitializedError:
        typer.echo("Error: gstack is already initialized. Use --force to reinitialize.", err=True)
        raise typer.Exit(1)
    except GitError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)


@app.command()
def create(
    name: str = typer.Argument(..., help="Name of the new branch"),
    parent: Optional[str] = typer.Option(
        None, "--parent", "-p", help="Parent branch (defaults to current branch)"
    ),
) -> None:
    """Create a new stacked branch."""
    repo_root = get_repo_root_or_exit()

    try:
        stack_manager.require_initialized(repo_root)
    except NotInitializedError:
        typer.echo("Error: gstack is not initialized. Run 'gstack init' first.", err=True)
        raise typer.Exit(1)

    # Check for clean workdir
    try:
        git_ops.require_clean_workdir()
    except DirtyWorkdirError:
        typer.echo(
            "Error: Working directory is not clean. Commit or stash your changes first.",
            err=True,
        )
        raise typer.Exit(1)

    # Check if branch already exists
    if git_ops.branch_exists(name):
        typer.echo(f"Error: Branch '{name}' already exists.", err=True)
        raise typer.Exit(1)

    # Determine parent branch
    if parent is None:
        parent = git_ops.get_current_branch()

    # Create the git branch
    try:
        git_ops.checkout_branch(name, create=True)
    except GitError as e:
        typer.echo(f"Error creating branch: {e}", err=True)
        raise typer.Exit(1)

    # Register in config
    stack_manager.register_branch(name, parent=parent, repo_root=repo_root)

    typer.echo(f"Created branch '{name}' on top of '{parent}'.")


@app.command()
def sync() -> None:
    """Rebase the current stack onto the latest trunk."""
    typer.echo("gstack sync - not yet implemented")


@app.command(name="continue")
def continue_() -> None:
    """Continue a sync after resolving conflicts."""
    typer.echo("gstack continue - not yet implemented")


@app.command()
def abort() -> None:
    """Abort the current sync operation."""
    typer.echo("gstack abort - not yet implemented")


@app.command()
def submit() -> None:
    """Push branches and create/update GitHub PRs."""
    typer.echo("gstack submit - not yet implemented")


@app.command()
def log() -> None:
    """Show the current stack structure."""
    repo_root = get_repo_root_or_exit()

    try:
        stack_manager.require_initialized(repo_root)
    except NotInitializedError:
        typer.echo("Error: gstack is not initialized. Run 'gstack init' first.", err=True)
        raise typer.Exit(1)

    config = stack_manager.load_config(repo_root)
    current_branch = git_ops.get_current_branch()

    if not config.branches:
        typer.echo(f"No stacked branches. Trunk: {config.trunk}")
        return

    # Build tree visualization
    def print_branch(branch: str, indent: int = 0) -> None:
        prefix = "  " * indent
        marker = "* " if branch == current_branch else "  "
        info = config.branches.get(branch)
        pr_info = ""
        if info and info.pr_url:
            pr_info = f" ({info.pr_url})"
        typer.echo(f"{prefix}{marker}{branch}{pr_info}")

        # Print children
        if info:
            for child in info.children:
                print_branch(child, indent + 1)

    # Print trunk
    typer.echo(f"Trunk: {config.trunk}")

    # Find root branches (branches whose parent is trunk)
    root_branches = [
        name for name, info in config.branches.items() if info.parent == config.trunk
    ]

    for branch in root_branches:
        print_branch(branch, indent=1)


@app.command()
def delete(
    name: str = typer.Argument(..., help="Name of the branch to delete"),
    force: bool = typer.Option(
        False, "--force", "-f", help="Force delete even if branch has unmerged changes"
    ),
) -> None:
    """Delete a branch from the stack."""
    repo_root = get_repo_root_or_exit()

    try:
        stack_manager.require_initialized(repo_root)
    except NotInitializedError:
        typer.echo("Error: gstack is not initialized. Run 'gstack init' first.", err=True)
        raise typer.Exit(1)

    config = stack_manager.load_config(repo_root)

    # Check if branch is tracked
    if name not in config.branches:
        typer.echo(f"Error: Branch '{name}' is not tracked by gstack.", err=True)
        raise typer.Exit(1)

    # Check if we're on the branch to delete
    current_branch = git_ops.get_current_branch()
    if current_branch == name:
        typer.echo(
            f"Error: Cannot delete the current branch. Checkout a different branch first.",
            err=True,
        )
        raise typer.Exit(1)

    # Unregister from config (handles reparenting)
    stack_manager.unregister_branch(name, repo_root=repo_root)

    # Delete the git branch
    try:
        git_ops.delete_branch(name, force=force)
        typer.echo(f"Deleted branch '{name}'.")
    except GitError as e:
        # Branch might already be deleted in git, that's ok
        if "not found" not in str(e).lower():
            typer.echo(f"Warning: Could not delete git branch: {e}", err=True)
        else:
            typer.echo(f"Removed '{name}' from gstack (git branch already deleted).")


if __name__ == "__main__":
    app()
