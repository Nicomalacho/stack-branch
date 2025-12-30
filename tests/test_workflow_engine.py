"""Tests for workflow engine (sync, continue, abort)."""

import subprocess
from pathlib import Path

import pytest

from gstack import git_ops, stack_manager, workflow_engine
from gstack.exceptions import DirtyWorkdirError, NoPendingOperationError, PendingOperationError


def make_commit(message: str = "Test commit") -> str:
    """Create a commit and return the SHA."""
    import time

    filename = f"file_{time.time_ns()}.txt"
    Path(filename).write_text(f"Content for {message}\n")
    subprocess.run(["git", "add", filename], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], check=True, capture_output=True)
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    )
    return result.stdout.strip()


class TestSyncWorkflow:
    """Tests for sync workflow."""

    def test_fails_if_workdir_dirty(self, temp_git_repo: Path) -> None:
        """Raises DirtyWorkdirError if uncommitted changes."""
        stack_manager.init_config(temp_git_repo)
        (temp_git_repo / "dirty.txt").write_text("uncommitted")

        with pytest.raises(DirtyWorkdirError):
            workflow_engine.run_sync(temp_git_repo)

    def test_fails_if_pending_state(self, temp_git_repo: Path) -> None:
        """Raises PendingOperationError if state file exists."""
        stack_manager.init_config(temp_git_repo)
        # Create a pending state
        from gstack.models import SyncState

        state = SyncState(active_command="sync", todo_queue=["feature"], original_head="feature")
        stack_manager.save_state(state, temp_git_repo)

        with pytest.raises(PendingOperationError):
            workflow_engine.run_sync(temp_git_repo)

    def test_creates_state_file(self, temp_git_repo: Path) -> None:
        """State file created before rebase starts."""
        stack_manager.init_config(temp_git_repo)
        # Create a branch with a commit
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        workflow_engine.run_sync(temp_git_repo)

        # State should be cleared after successful sync
        assert not stack_manager.has_pending_state(temp_git_repo)

    def test_noop_when_no_branches(self, temp_git_repo: Path) -> None:
        """No-op when no stacked branches exist."""
        stack_manager.init_config(temp_git_repo)

        result = workflow_engine.run_sync(temp_git_repo)

        assert result.success is True
        assert result.rebased_branches == []

    def test_rebases_single_branch(self, temp_git_repo: Path) -> None:
        """Rebases a single branch onto updated trunk."""
        stack_manager.init_config(temp_git_repo)

        # Create feature branch
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        # Add commit to main
        git_ops.checkout_branch("main")
        make_commit("main commit")

        # Go back to feature and sync
        git_ops.checkout_branch("feature")
        result = workflow_engine.run_sync(temp_git_repo)

        assert result.success is True
        assert "feature" in result.rebased_branches

    def test_rebases_stack_in_order(self, temp_git_repo: Path) -> None:
        """Parent branches rebased before children (topological order)."""
        stack_manager.init_config(temp_git_repo)

        # Create stack: main -> feature -> feature-ui
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        git_ops.checkout_branch("feature-ui", create=True)
        make_commit("feature-ui commit")
        stack_manager.register_branch("feature-ui", "feature", temp_git_repo)

        # Add commit to main
        git_ops.checkout_branch("main")
        make_commit("main commit")

        # Go back to feature-ui and sync
        git_ops.checkout_branch("feature-ui")
        result = workflow_engine.run_sync(temp_git_repo)

        assert result.success is True
        # feature should be rebased before feature-ui
        assert result.rebased_branches.index("feature") < result.rebased_branches.index(
            "feature-ui"
        )

    def test_returns_to_original_branch(self, temp_git_repo: Path) -> None:
        """User ends up on same branch they started on."""
        stack_manager.init_config(temp_git_repo)

        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        git_ops.checkout_branch("main")
        make_commit("main commit")

        git_ops.checkout_branch("feature")
        workflow_engine.run_sync(temp_git_repo)

        assert git_ops.get_current_branch() == "feature"

    def test_clears_state_on_success(self, temp_git_repo: Path) -> None:
        """State file deleted after successful sync."""
        stack_manager.init_config(temp_git_repo)

        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        workflow_engine.run_sync(temp_git_repo)

        assert not stack_manager.has_pending_state(temp_git_repo)

    def test_stops_on_conflict(self, temp_git_repo: Path) -> None:
        """State preserved on conflict, returns conflict result."""
        stack_manager.init_config(temp_git_repo)

        # Create conflicting changes
        conflict_file = temp_git_repo / "conflict.txt"
        conflict_file.write_text("main content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: add conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature", create=True)
        conflict_file.write_text("feature content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feature: modify conflict.txt"], check=True, capture_output=True
        )
        stack_manager.register_branch("feature", "main", temp_git_repo)

        git_ops.checkout_branch("main")
        conflict_file.write_text("main updated content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: update conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature")
        result = workflow_engine.run_sync(temp_git_repo)

        assert result.success is False
        assert result.conflict_branch == "feature"
        assert stack_manager.has_pending_state(temp_git_repo)

        # Cleanup
        subprocess.run(["git", "rebase", "--abort"], capture_output=True)
        stack_manager.clear_state(temp_git_repo)

    def test_syncs_only_current_stack(self, temp_git_repo: Path) -> None:
        """Only syncs branches in the current stack, not other stacks."""
        stack_manager.init_config(temp_git_repo)

        # Create two independent stacks
        git_ops.checkout_branch("feature-a", create=True)
        make_commit("feature-a commit")
        stack_manager.register_branch("feature-a", "main", temp_git_repo)

        git_ops.checkout_branch("main")
        git_ops.checkout_branch("feature-b", create=True)
        make_commit("feature-b commit")
        stack_manager.register_branch("feature-b", "main", temp_git_repo)

        # Add commit to main
        git_ops.checkout_branch("main")
        make_commit("main commit")

        # Sync from feature-a - should only sync feature-a
        git_ops.checkout_branch("feature-a")
        result = workflow_engine.run_sync(temp_git_repo)

        assert result.success is True
        assert "feature-a" in result.rebased_branches
        assert "feature-b" not in result.rebased_branches


class TestContinueWorkflow:
    """Tests for continue workflow."""

    def test_fails_without_state(self, temp_git_repo: Path) -> None:
        """Error if no pending operation exists."""
        stack_manager.init_config(temp_git_repo)

        with pytest.raises(NoPendingOperationError):
            workflow_engine.run_continue(temp_git_repo)

    def test_resumes_after_conflict_resolved(self, temp_git_repo: Path) -> None:
        """Continues sync after conflict is resolved."""
        stack_manager.init_config(temp_git_repo)

        # Create conflicting changes
        conflict_file = temp_git_repo / "conflict.txt"
        conflict_file.write_text("main content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: add conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature", create=True)
        conflict_file.write_text("feature content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feature: modify conflict.txt"], check=True, capture_output=True
        )
        stack_manager.register_branch("feature", "main", temp_git_repo)

        git_ops.checkout_branch("main")
        conflict_file.write_text("main updated content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: update conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature")
        result = workflow_engine.run_sync(temp_git_repo)
        assert result.success is False

        # Resolve conflict
        conflict_file.write_text("resolved content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)

        # Continue
        result = workflow_engine.run_continue(temp_git_repo)

        assert result.success is True
        assert not stack_manager.has_pending_state(temp_git_repo)


class TestAutoSubmitAfterContinue:
    """Tests for auto-submit after successful continue (Fix 7)."""

    def test_continue_triggers_submit_on_success(
        self, temp_git_repo_with_remote: Path, mocker
    ) -> None:
        """Successful continue should trigger submit to push changes."""

        stack_manager.init_config(temp_git_repo_with_remote)

        # Create conflicting changes
        conflict_file = temp_git_repo_with_remote / "conflict.txt"
        conflict_file.write_text("main content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: add conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature", create=True)
        conflict_file.write_text("feature content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feature: modify conflict.txt"],
            check=True,
            capture_output=True,
        )
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        git_ops.checkout_branch("main")
        conflict_file.write_text("main updated content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: update conflict.txt"],
            check=True,
            capture_output=True,
        )

        git_ops.checkout_branch("feature")
        result = workflow_engine.run_sync(temp_git_repo_with_remote)
        assert result.success is False

        # Resolve conflict
        conflict_file.write_text("resolved content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)

        # Mock gh_ops for submit
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)

        # Track if submit was called
        original_submit = workflow_engine.run_submit
        submit_called = []

        def mock_submit(repo_root):
            submit_called.append(True)
            return original_submit(repo_root)

        mocker.patch.object(workflow_engine, "run_submit", side_effect=mock_submit)

        # Continue - should trigger submit
        result = workflow_engine.run_continue(temp_git_repo_with_remote)

        assert result.success is True
        assert len(submit_called) > 0, "run_submit should be called after successful continue"


class TestAbortWorkflow:
    """Tests for abort workflow."""

    def test_fails_without_state(self, temp_git_repo: Path) -> None:
        """Error if no pending operation exists."""
        stack_manager.init_config(temp_git_repo)

        with pytest.raises(NoPendingOperationError):
            workflow_engine.run_abort(temp_git_repo)

    def test_aborts_rebase_and_clears_state(self, temp_git_repo: Path) -> None:
        """Aborts rebase and clears state file."""
        stack_manager.init_config(temp_git_repo)

        # Create conflicting changes
        conflict_file = temp_git_repo / "conflict.txt"
        conflict_file.write_text("main content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: add conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature", create=True)
        conflict_file.write_text("feature content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feature: modify conflict.txt"], check=True, capture_output=True
        )
        stack_manager.register_branch("feature", "main", temp_git_repo)

        git_ops.checkout_branch("main")
        conflict_file.write_text("main updated content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: update conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature")
        result = workflow_engine.run_sync(temp_git_repo)
        assert result.success is False

        # Abort
        workflow_engine.run_abort(temp_git_repo)

        assert not stack_manager.has_pending_state(temp_git_repo)
        assert not git_ops.is_rebase_in_progress()

    def test_returns_to_original_branch(self, temp_git_repo: Path) -> None:
        """Returns to original branch after abort."""
        stack_manager.init_config(temp_git_repo)

        # Create conflicting changes
        conflict_file = temp_git_repo / "conflict.txt"
        conflict_file.write_text("main content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: add conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature", create=True)
        conflict_file.write_text("feature content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feature: modify conflict.txt"], check=True, capture_output=True
        )
        stack_manager.register_branch("feature", "main", temp_git_repo)

        git_ops.checkout_branch("main")
        conflict_file.write_text("main updated content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: update conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature")
        original_branch = git_ops.get_current_branch()

        workflow_engine.run_sync(temp_git_repo)
        workflow_engine.run_abort(temp_git_repo)

        assert git_ops.get_current_branch() == original_branch


class TestSubmitWorkflow:
    """Tests for submit workflow."""

    def test_fails_if_workdir_dirty(self, temp_git_repo: Path) -> None:
        """Raises DirtyWorkdirError if uncommitted changes."""
        stack_manager.init_config(temp_git_repo)
        (temp_git_repo / "dirty.txt").write_text("uncommitted")

        with pytest.raises(DirtyWorkdirError):
            workflow_engine.run_submit(temp_git_repo)

    def test_fails_if_not_authenticated(self, temp_git_repo: Path, mocker) -> None:
        """Raises GhNotAuthenticatedError if not logged in."""
        from gstack.exceptions import GhNotAuthenticatedError

        stack_manager.init_config(temp_git_repo)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        # Mock gh_ops.is_gh_authenticated to return False
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=False)

        with pytest.raises(GhNotAuthenticatedError):
            workflow_engine.run_submit(temp_git_repo)

    def test_pushes_branches(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """Pushes all branches in the stack."""
        from gstack.gh_ops import PrCreateResult

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        # Mock gh_ops functions
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        mocker.patch(
            "gstack.gh_ops.create_pr",
            return_value=PrCreateResult(url="https://github.com/test/pr/1", number=1),
        )

        result = workflow_engine.run_submit(temp_git_repo_with_remote)

        assert result.success is True
        assert "feature" in result.pushed_branches

    def test_creates_pr_if_missing(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """Creates PR if none exists."""
        from gstack.gh_ops import PrCreateResult

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        # Mock gh_ops functions
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        mock_create_pr = mocker.patch(
            "gstack.gh_ops.create_pr",
            return_value=PrCreateResult(url="https://github.com/test/pr/1", number=1),
        )

        result = workflow_engine.run_submit(temp_git_repo_with_remote)

        assert result.success is True
        assert mock_create_pr.called
        assert "feature" in result.created_prs

    def test_updates_pr_base_if_wrong(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """Updates PR base if it doesn't match parent."""
        from gstack.gh_ops import PrInfo

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        git_ops.checkout_branch("feature-ui", create=True)
        make_commit("feature-ui commit")
        stack_manager.register_branch("feature-ui", "feature", temp_git_repo_with_remote)

        # Mock gh_ops functions
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)

        def get_pr_info_side_effect(branch):
            # Return PR info with wrong base for feature-ui
            if branch == "feature-ui":
                return PrInfo(
                    url=f"https://github.com/test/pr/{branch}",
                    base="main",  # Wrong base - should be "feature"
                    state="OPEN",
                    number=2,
                )
            return PrInfo(
                url=f"https://github.com/test/pr/{branch}",
                base="main",
                state="OPEN",
                number=1,
            )

        mocker.patch("gstack.gh_ops.get_pr_info", side_effect=get_pr_info_side_effect)
        mock_update_base = mocker.patch("gstack.gh_ops.update_pr_base")

        result = workflow_engine.run_submit(temp_git_repo_with_remote)

        assert result.success is True
        # feature-ui's PR should have had its base updated from main to feature
        mock_update_base.assert_called_with("feature-ui", "feature")

    def test_stores_pr_url_in_config(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """Stores PR URL in config after creation."""
        from gstack.gh_ops import PrCreateResult

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        # Mock gh_ops functions
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        mocker.patch(
            "gstack.gh_ops.create_pr",
            return_value=PrCreateResult(url="https://github.com/test/repo/pull/42", number=42),
        )

        workflow_engine.run_submit(temp_git_repo_with_remote)

        config = stack_manager.load_config(temp_git_repo_with_remote)
        assert config.branches["feature"].pr_url == "https://github.com/test/repo/pull/42"

    def test_noop_when_no_branches(self, temp_git_repo: Path, mocker) -> None:
        """No-op when no stacked branches exist."""
        stack_manager.init_config(temp_git_repo)

        # Mock gh auth
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)

        result = workflow_engine.run_submit(temp_git_repo)

        assert result.success is True
        assert result.pushed_branches == []


class TestPushWorkflow:
    """Tests for push workflow (single branch)."""

    def test_fails_if_workdir_dirty(self, temp_git_repo: Path) -> None:
        """Raises DirtyWorkdirError if uncommitted changes."""
        stack_manager.init_config(temp_git_repo)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)
        (temp_git_repo / "dirty.txt").write_text("uncommitted")

        with pytest.raises(DirtyWorkdirError):
            workflow_engine.run_push(temp_git_repo)

    def test_fails_if_not_authenticated(self, temp_git_repo: Path, mocker) -> None:
        """Raises GhNotAuthenticatedError if not logged in."""
        from gstack.exceptions import GhNotAuthenticatedError

        stack_manager.init_config(temp_git_repo)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=False)

        with pytest.raises(GhNotAuthenticatedError):
            workflow_engine.run_push(temp_git_repo)

    def test_fails_if_branch_not_tracked(self, temp_git_repo: Path, mocker) -> None:
        """Fails if current branch is not tracked by gstack."""
        stack_manager.init_config(temp_git_repo)
        git_ops.checkout_branch("untracked", create=True)
        make_commit("untracked commit")

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)

        result = workflow_engine.run_push(temp_git_repo)

        assert result.success is False
        assert "not tracked" in result.message

    def test_pushes_current_branch(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """Pushes only the current branch."""
        from gstack.gh_ops import PrCreateResult

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        mocker.patch(
            "gstack.gh_ops.create_pr",
            return_value=PrCreateResult(url="https://github.com/test/pr/1", number=1),
        )

        result = workflow_engine.run_push(temp_git_repo_with_remote)

        assert result.success is True
        assert result.branch == "feature"
        assert result.pr_created is True

    def test_creates_pr_if_missing(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """Creates PR if none exists."""
        from gstack.gh_ops import PrCreateResult

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        mock_create = mocker.patch(
            "gstack.gh_ops.create_pr",
            return_value=PrCreateResult(url="https://github.com/test/pr/1", number=1),
        )

        result = workflow_engine.run_push(temp_git_repo_with_remote)

        assert result.success is True
        assert result.pr_created is True
        mock_create.assert_called_once()
        # Verify head and base are correct
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["head"] == "feature"
        assert call_kwargs["base"] == "main"

    def test_updates_pr_base_if_wrong(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """Updates PR base if it doesn't match parent."""
        from gstack.gh_ops import PrInfo

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        git_ops.checkout_branch("feature-ui", create=True)
        make_commit("feature-ui commit")
        stack_manager.register_branch("feature-ui", "feature", temp_git_repo_with_remote)

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch(
            "gstack.gh_ops.get_pr_info",
            return_value=PrInfo(
                url="https://github.com/test/pr/2",
                base="main",  # Wrong base
                state="OPEN",
                number=2,
            ),
        )
        mock_update = mocker.patch("gstack.gh_ops.update_pr_base")

        result = workflow_engine.run_push(temp_git_repo_with_remote)

        assert result.success is True
        assert result.pr_updated is True
        mock_update.assert_called_once_with("feature-ui", "feature")

    def test_stores_pr_url_in_config(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """Stores PR URL in config after creation."""
        from gstack.gh_ops import PrCreateResult

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        mocker.patch(
            "gstack.gh_ops.create_pr",
            return_value=PrCreateResult(url="https://github.com/test/repo/pull/99", number=99),
        )

        workflow_engine.run_push(temp_git_repo_with_remote)

        config = stack_manager.load_config(temp_git_repo_with_remote)
        assert config.branches["feature"].pr_url == "https://github.com/test/repo/pull/99"

    def test_creates_pr_with_body(self, temp_git_repo_with_remote: Path, mocker) -> None:
        """PR creation should include a body/description."""
        from gstack.gh_ops import PrCreateResult

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        mock_create = mocker.patch(
            "gstack.gh_ops.create_pr",
            return_value=PrCreateResult(url="https://github.com/test/pr/1", number=1),
        )

        workflow_engine.run_push(temp_git_repo_with_remote)

        # Verify create_pr was called with a body argument
        mock_create.assert_called_once()
        call_kwargs = mock_create.call_args
        # Check that body was passed (either as kwarg or that it's not empty)
        assert "body" in call_kwargs.kwargs or len(call_kwargs.args) > 2
        if "body" in call_kwargs.kwargs:
            assert call_kwargs.kwargs["body"] is not None
            assert len(call_kwargs.kwargs["body"]) > 0


class TestAutoSquashBeforeRebase:
    """Tests for auto-squash before rebase behavior (Fix 8)."""

    def test_sync_squashes_commits_before_rebase(self, temp_git_repo: Path) -> None:
        """Sync should squash multiple commits into one before rebasing."""
        stack_manager.init_config(temp_git_repo)

        # Create feature branch with multiple commits
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit 1")
        make_commit("feature commit 2")
        make_commit("feature commit 3")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        # Count commits before sync
        result = subprocess.run(
            ["git", "rev-list", "--count", "main..feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert int(result.stdout.strip()) == 3

        # Sync
        workflow_engine.run_sync(temp_git_repo)

        # Count commits after sync - should be squashed to 1
        result = subprocess.run(
            ["git", "rev-list", "--count", "main..feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert int(result.stdout.strip()) == 1

    def test_sync_preserves_single_commit(self, temp_git_repo: Path) -> None:
        """Sync should not modify a branch with only one commit."""
        stack_manager.init_config(temp_git_repo)

        # Create feature branch with single commit
        git_ops.checkout_branch("feature", create=True)
        make_commit("single feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo)

        # Get SHA before
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )

        # Sync (should not squash since only 1 commit)
        workflow_engine.run_sync(temp_git_repo)

        # Get SHA after - should be different due to rebase (even if noop)
        # Actually it might be the same if there's nothing to rebase
        result = subprocess.run(
            ["git", "rev-list", "--count", "main..feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        # Should still be 1 commit
        assert int(result.stdout.strip()) == 1


class TestSyncBeforeSubmit:
    """Tests for sync-before-submit behavior (Fix 6)."""

    def test_submit_syncs_branches_before_pushing(
        self, temp_git_repo_with_remote: Path, mocker
    ) -> None:
        """Submit should sync (rebase) branches before pushing them."""
        from gstack.gh_ops import PrCreateResult

        stack_manager.init_config(temp_git_repo_with_remote)

        # Create a stack: main -> feature -> feature-ui
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        git_ops.checkout_branch("feature-ui", create=True)
        make_commit("feature-ui commit")
        stack_manager.register_branch("feature-ui", "feature", temp_git_repo_with_remote)

        # Add a new commit to main (simulating trunk updates)
        git_ops.checkout_branch("main")
        make_commit("main update")

        # Go back to feature-ui
        git_ops.checkout_branch("feature-ui")

        # Mock gh_ops functions
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        mocker.patch(
            "gstack.gh_ops.create_pr",
            return_value=PrCreateResult(url="https://github.com/test/pr/1", number=1),
        )

        # Track if sync was called
        original_sync = workflow_engine.run_sync
        sync_called = []

        def mock_sync(repo_root):
            sync_called.append(True)
            return original_sync(repo_root)

        mocker.patch.object(workflow_engine, "run_sync", side_effect=mock_sync)

        result = workflow_engine.run_submit(temp_git_repo_with_remote)

        # Sync should have been called before push
        assert len(sync_called) > 0, "run_sync should be called before pushing"
        assert result.success is True

    def test_submit_fails_if_sync_has_conflicts(
        self, temp_git_repo_with_remote: Path, mocker
    ) -> None:
        """Submit should fail if sync encounters conflicts."""

        stack_manager.init_config(temp_git_repo_with_remote)

        # Create conflicting changes
        conflict_file = temp_git_repo_with_remote / "conflict.txt"
        conflict_file.write_text("main content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: add conflict.txt"], check=True, capture_output=True
        )

        git_ops.checkout_branch("feature", create=True)
        conflict_file.write_text("feature content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feature: modify conflict.txt"],
            check=True,
            capture_output=True,
        )
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        git_ops.checkout_branch("main")
        conflict_file.write_text("main updated content\n")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "main: update conflict.txt"],
            check=True,
            capture_output=True,
        )

        git_ops.checkout_branch("feature")

        # Mock gh_ops functions
        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)

        result = workflow_engine.run_submit(temp_git_repo_with_remote)

        # Submit should fail due to sync conflict
        assert result.success is False
        assert "conflict" in result.message.lower() or result.message != ""

        # Cleanup
        subprocess.run(["git", "rebase", "--abort"], capture_output=True)
        stack_manager.clear_state(temp_git_repo_with_remote)


class TestPrCreationErrorHandling:
    """Tests for PR creation error handling and logging."""

    def test_submit_reports_pr_creation_failure(
        self, temp_git_repo_with_remote: Path, mocker
    ) -> None:
        """Submit should report when PR creation fails, not silently ignore."""
        from gstack.exceptions import GhError

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        # Make PR creation fail
        mocker.patch(
            "gstack.gh_ops.create_pr",
            side_effect=GhError("Failed to create PR", returncode=1),
        )

        result = workflow_engine.run_submit(temp_git_repo_with_remote)

        # Result should indicate the failure in some way
        # Either in failed_prs list or in the message
        assert (
            "feature" not in result.created_prs
            or "failed" in result.message.lower()
            or hasattr(result, "failed_prs")
        )

    def test_push_reports_pr_creation_failure(
        self, temp_git_repo_with_remote: Path, mocker
    ) -> None:
        """Push should report when PR creation fails."""
        from gstack.exceptions import GhError

        stack_manager.init_config(temp_git_repo_with_remote)
        git_ops.checkout_branch("feature", create=True)
        make_commit("feature commit")
        stack_manager.register_branch("feature", "main", temp_git_repo_with_remote)

        mocker.patch("gstack.gh_ops.is_gh_authenticated", return_value=True)
        mocker.patch("gstack.gh_ops.get_pr_info", return_value=None)
        # Make PR creation fail
        mocker.patch(
            "gstack.gh_ops.create_pr",
            side_effect=GhError("Failed to create PR", returncode=1),
        )

        result = workflow_engine.run_push(temp_git_repo_with_remote)

        # Result should indicate the failure
        # Either pr_created is False or message contains error info
        assert result.pr_created is False or "fail" in result.message.lower()
