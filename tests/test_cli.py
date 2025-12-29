"""Tests for gstack CLI commands."""

import subprocess
from pathlib import Path

from typer.testing import CliRunner

from gstack import stack_manager
from gstack.main import app

runner = CliRunner()


class TestInitCommand:
    """Tests for gstack init command."""

    def test_creates_config_file(self, temp_git_repo: Path) -> None:
        """gstack init creates .gstack_config.json."""
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert (temp_git_repo / ".gstack_config.json").exists()

    def test_auto_detects_trunk(self, temp_git_repo: Path) -> None:
        """Trunk auto-detected from repo."""
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        config = stack_manager.load_config(temp_git_repo)
        assert config.trunk == "main"

    def test_explicit_trunk_option(self, temp_git_repo: Path) -> None:
        """Can specify trunk with --trunk option."""
        result = runner.invoke(app, ["init", "--trunk", "develop"])

        assert result.exit_code == 0
        config = stack_manager.load_config(temp_git_repo)
        assert config.trunk == "develop"

    def test_short_trunk_option(self, temp_git_repo: Path) -> None:
        """Can specify trunk with -t option."""
        result = runner.invoke(app, ["init", "-t", "master"])

        assert result.exit_code == 0
        config = stack_manager.load_config(temp_git_repo)
        assert config.trunk == "master"

    def test_shows_success_message(self, temp_git_repo: Path) -> None:
        """Shows success message after init."""
        result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        assert "initialized" in result.stdout.lower()

    def test_fails_if_already_initialized(self, temp_git_repo: Path) -> None:
        """Fails if already initialized."""
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["init"])

        assert result.exit_code != 0
        assert "already" in result.stdout.lower()

    def test_force_reinitializes(self, temp_git_repo: Path) -> None:
        """--force flag allows reinitialization."""
        runner.invoke(app, ["init"])
        # Add a branch to the config
        config = stack_manager.load_config(temp_git_repo)
        config.add_branch("feature", parent="main")
        stack_manager.save_config(config, temp_git_repo)

        result = runner.invoke(app, ["init", "--force"])

        assert result.exit_code == 0
        config = stack_manager.load_config(temp_git_repo)
        assert config.branches == {}

    def test_fails_outside_git_repo(self, tmp_path: Path) -> None:
        """Fails when run outside a git repository."""
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            result = runner.invoke(app, ["init"])
            assert result.exit_code != 0
            assert "not a git repository" in result.stdout.lower()
        finally:
            os.chdir(original_cwd)


class TestCreateCommand:
    """Tests for gstack create command."""

    def test_creates_git_branch(self, temp_git_repo: Path) -> None:
        """Creates a new git branch."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["create", "feature-login"])

        assert result.exit_code == 0
        # Verify branch exists in git
        git_result = subprocess.run(
            ["git", "rev-parse", "--verify", "refs/heads/feature-login"],
            capture_output=True,
        )
        assert git_result.returncode == 0

    def test_switches_to_new_branch(self, temp_git_repo: Path) -> None:
        """Switches to the newly created branch."""
        runner.invoke(app, ["init"])

        runner.invoke(app, ["create", "feature-login"])

        # Verify we're on the new branch
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
        )
        assert result.stdout.strip() == "feature-login"

    def test_registers_branch_in_config(self, temp_git_repo: Path) -> None:
        """Registers the new branch in gstack config."""
        runner.invoke(app, ["init"])

        runner.invoke(app, ["create", "feature-login"])

        config = stack_manager.load_config(temp_git_repo)
        assert "feature-login" in config.branches
        assert config.branches["feature-login"].parent == "main"

    def test_creates_stacked_branch(self, temp_git_repo: Path) -> None:
        """Can create a branch stacked on another branch."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature-login"])

        runner.invoke(app, ["create", "feature-login-ui"])

        config = stack_manager.load_config(temp_git_repo)
        assert config.branches["feature-login-ui"].parent == "feature-login"
        assert "feature-login-ui" in config.branches["feature-login"].children

    def test_shows_success_message(self, temp_git_repo: Path) -> None:
        """Shows success message after create."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["create", "feature-login"])

        assert result.exit_code == 0
        assert "feature-login" in result.stdout

    def test_fails_if_not_initialized(self, temp_git_repo: Path) -> None:
        """Fails if gstack not initialized."""
        result = runner.invoke(app, ["create", "feature-login"])

        assert result.exit_code != 0
        assert "not initialized" in result.stdout.lower() or "init" in result.stdout.lower()

    def test_fails_if_branch_exists(self, temp_git_repo: Path) -> None:
        """Fails if branch already exists in git."""
        runner.invoke(app, ["init"])
        subprocess.run(["git", "checkout", "-b", "existing"], check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        result = runner.invoke(app, ["create", "existing"])

        assert result.exit_code != 0
        assert "exists" in result.stdout.lower()

    def test_works_with_dirty_workdir(self, temp_git_repo: Path) -> None:
        """Works even if working directory has uncommitted changes."""
        runner.invoke(app, ["init"])
        (temp_git_repo / "newfile.txt").write_text("uncommitted")

        result = runner.invoke(app, ["create", "feature-login"])

        assert result.exit_code == 0
        assert "feature-login" in result.stdout

    def test_parent_option(self, temp_git_repo: Path) -> None:
        """Can specify parent with --parent option."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature-a"])
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        result = runner.invoke(app, ["create", "feature-b", "--parent", "feature-a"])

        assert result.exit_code == 0
        config = stack_manager.load_config(temp_git_repo)
        assert config.branches["feature-b"].parent == "feature-a"


class TestLogCommand:
    """Tests for gstack log command."""

    def test_shows_empty_stack(self, temp_git_repo: Path) -> None:
        """Shows message when no stacked branches exist."""
        runner.invoke(app, ["init"])

        result = runner.invoke(app, ["log"])

        assert result.exit_code == 0

    def test_shows_single_branch(self, temp_git_repo: Path) -> None:
        """Shows a single stacked branch."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature"])

        result = runner.invoke(app, ["log"])

        assert result.exit_code == 0
        assert "feature" in result.stdout

    def test_shows_stack_hierarchy(self, temp_git_repo: Path) -> None:
        """Shows branches in stack hierarchy."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature"])
        runner.invoke(app, ["create", "feature-ui"])

        result = runner.invoke(app, ["log"])

        assert result.exit_code == 0
        assert "feature" in result.stdout
        assert "feature-ui" in result.stdout

    def test_indicates_current_branch(self, temp_git_repo: Path) -> None:
        """Indicates which branch is currently checked out."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature"])

        result = runner.invoke(app, ["log"])

        # Should show some indicator for current branch
        assert result.exit_code == 0


class TestDeleteCommand:
    """Tests for gstack delete command."""

    def test_removes_branch_from_config(self, temp_git_repo: Path) -> None:
        """Removes branch from gstack config."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature"])
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        result = runner.invoke(app, ["delete", "feature"])

        assert result.exit_code == 0
        config = stack_manager.load_config(temp_git_repo)
        assert "feature" not in config.branches

    def test_deletes_git_branch(self, temp_git_repo: Path) -> None:
        """Deletes the git branch."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature"])
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        runner.invoke(app, ["delete", "feature"])

        git_result = subprocess.run(
            ["git", "rev-parse", "--verify", "refs/heads/feature"],
            capture_output=True,
        )
        assert git_result.returncode != 0

    def test_reparents_children(self, temp_git_repo: Path) -> None:
        """Reparents child branches to grandparent."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature"])
        runner.invoke(app, ["create", "feature-ui"])
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        runner.invoke(app, ["delete", "feature", "--force"])

        config = stack_manager.load_config(temp_git_repo)
        assert "feature" not in config.branches
        assert config.branches["feature-ui"].parent == "main"

    def test_fails_if_branch_not_tracked(self, temp_git_repo: Path) -> None:
        """Fails if branch is not tracked by gstack."""
        runner.invoke(app, ["init"])
        subprocess.run(["git", "checkout", "-b", "untracked"], check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        result = runner.invoke(app, ["delete", "untracked"])

        assert result.exit_code != 0

    def test_fails_if_on_branch_to_delete(self, temp_git_repo: Path) -> None:
        """Fails if trying to delete the current branch."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature"])

        result = runner.invoke(app, ["delete", "feature"])

        assert result.exit_code != 0
        assert "current" in result.stdout.lower() or "checkout" in result.stdout.lower()


class TestSubmitCommand:
    """Tests for gstack submit command."""

    def test_fails_if_not_initialized(self, temp_git_repo: Path) -> None:
        """Fails if gstack not initialized."""
        result = runner.invoke(app, ["submit"])

        assert result.exit_code != 0
        assert "not initialized" in result.stdout.lower() or "init" in result.stdout.lower()

    def test_fails_if_workdir_dirty(self, temp_git_repo: Path) -> None:
        """Fails if working directory has uncommitted changes."""
        runner.invoke(app, ["init"])
        (temp_git_repo / "dirty.txt").write_text("uncommitted")

        result = runner.invoke(app, ["submit"])

        assert result.exit_code != 0
        assert "clean" in result.stdout.lower() or "uncommitted" in result.stdout.lower()

    def test_fails_if_not_authenticated(self, temp_git_repo: Path, mocker) -> None:
        """Fails if GitHub CLI is not authenticated."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["create", "feature"])

        # Mock gh auth to fail
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=False)

        result = runner.invoke(app, ["submit"])

        assert result.exit_code != 0
        assert "authenticated" in result.stdout.lower() or "gh auth" in result.stdout.lower()

    def test_noop_when_no_branches(self, temp_git_repo: Path, mocker) -> None:
        """No-op when no stacked branches exist."""
        runner.invoke(app, ["init"])

        # Mock gh auth to succeed
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)

        result = runner.invoke(app, ["submit"])

        assert result.exit_code == 0
        assert "nothing" in result.stdout.lower()
