"""Tests for git operations wrapper."""

import subprocess
from pathlib import Path

import pytest

from gstack import git_ops
from gstack.exceptions import DirtyWorkdirError, GitError, NotAGitRepoError


class TestRunGit:
    """Tests for the run_git wrapper function."""

    def test_captures_stdout(self, temp_git_repo: Path) -> None:
        """Output is captured correctly."""
        result = git_ops.run_git("status", "--porcelain")
        assert isinstance(result.stdout, str)

    def test_captures_stderr(self, temp_git_repo: Path) -> None:
        """Stderr is captured correctly."""
        result = git_ops.run_git("status")
        assert isinstance(result.stderr, str)

    def test_returns_returncode(self, temp_git_repo: Path) -> None:
        """Return code is available."""
        result = git_ops.run_git("status")
        assert result.returncode == 0

    def test_raises_on_failure(self, temp_git_repo: Path) -> None:
        """GitError raised with raw output on non-zero exit."""
        with pytest.raises(GitError) as exc_info:
            git_ops.run_git("checkout", "nonexistent-branch")
        assert "nonexistent-branch" in str(exc_info.value) or exc_info.value.stderr

    def test_check_false_does_not_raise(self, temp_git_repo: Path) -> None:
        """With check=False, no exception is raised on failure."""
        result = git_ops.run_git("checkout", "nonexistent-branch", check=False)
        assert result.returncode != 0


class TestGetCurrentBranch:
    """Tests for get_current_branch."""

    def test_returns_current_branch(self, temp_git_repo: Path) -> None:
        """Returns the current branch name."""
        branch = git_ops.get_current_branch()
        assert branch == "main"

    def test_after_checkout(self, temp_git_repo: Path) -> None:
        """Returns correct branch after checkout."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)
        branch = git_ops.get_current_branch()
        assert branch == "feature"


class TestIsWorkdirClean:
    """Tests for is_workdir_clean."""

    def test_true_when_clean(self, temp_git_repo: Path) -> None:
        """Returns True when git status --porcelain is empty."""
        assert git_ops.is_workdir_clean() is True

    def test_false_with_untracked_file(self, temp_git_repo: Path) -> None:
        """Returns False when untracked files exist."""
        (temp_git_repo / "newfile.txt").write_text("content")
        assert git_ops.is_workdir_clean() is False

    def test_false_with_modified_file(self, temp_git_repo: Path) -> None:
        """Returns False when tracked files are modified."""
        (temp_git_repo / "README.md").write_text("modified content")
        assert git_ops.is_workdir_clean() is False

    def test_false_with_staged_changes(self, temp_git_repo: Path) -> None:
        """Returns False when there are staged changes."""
        (temp_git_repo / "README.md").write_text("modified content")
        subprocess.run(["git", "add", "README.md"], check=True, capture_output=True)
        assert git_ops.is_workdir_clean() is False


class TestRequireCleanWorkdir:
    """Tests for require_clean_workdir."""

    def test_passes_when_clean(self, temp_git_repo: Path) -> None:
        """Does not raise when workdir is clean."""
        git_ops.require_clean_workdir()  # Should not raise

    def test_raises_when_dirty(self, temp_git_repo: Path) -> None:
        """Raises DirtyWorkdirError when workdir has changes."""
        (temp_git_repo / "newfile.txt").write_text("content")
        with pytest.raises(DirtyWorkdirError):
            git_ops.require_clean_workdir()


class TestDetectTrunk:
    """Tests for detect_trunk."""

    def test_returns_main_when_exists(self, temp_git_repo: Path) -> None:
        """Returns 'main' when main branch exists."""
        trunk = git_ops.detect_trunk()
        assert trunk == "main"

    def test_returns_master_as_fallback(self, tmp_path: Path) -> None:
        """Returns 'master' when main doesn't exist but master does."""
        import os

        original_cwd = os.getcwd()
        repo_path = tmp_path / "master_repo"
        repo_path.mkdir()
        os.chdir(repo_path)

        try:
            # Initialize with master as default branch
            subprocess.run(["git", "init", "-b", "master"], check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], check=True, capture_output=True
            )
            subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
            Path("README.md").write_text("# Test\n")
            subprocess.run(["git", "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], check=True, capture_output=True)

            trunk = git_ops.detect_trunk()
            assert trunk == "master"
        finally:
            os.chdir(original_cwd)

    def test_raises_when_neither_exists(self, tmp_path: Path) -> None:
        """Raises GitError when neither main nor master exists."""
        import os

        original_cwd = os.getcwd()
        repo_path = tmp_path / "custom_repo"
        repo_path.mkdir()
        os.chdir(repo_path)

        try:
            # Initialize with custom branch name
            subprocess.run(["git", "init", "-b", "develop"], check=True, capture_output=True)
            subprocess.run(
                ["git", "config", "user.email", "test@test.com"], check=True, capture_output=True
            )
            subprocess.run(["git", "config", "user.name", "Test"], check=True, capture_output=True)
            Path("README.md").write_text("# Test\n")
            subprocess.run(["git", "add", "."], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", "init"], check=True, capture_output=True)

            with pytest.raises(GitError, match="Could not detect trunk branch"):
                git_ops.detect_trunk()
        finally:
            os.chdir(original_cwd)


class TestCheckoutBranch:
    """Tests for checkout_branch."""

    def test_switches_to_existing_branch(self, temp_git_repo: Path) -> None:
        """Can switch to an existing branch."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        git_ops.checkout_branch("feature")
        assert git_ops.get_current_branch() == "feature"

    def test_creates_new_branch(self, temp_git_repo: Path) -> None:
        """Can create and switch to a new branch."""
        git_ops.checkout_branch("new-feature", create=True)
        assert git_ops.get_current_branch() == "new-feature"

    def test_raises_for_nonexistent_branch(self, temp_git_repo: Path) -> None:
        """Raises GitError for non-existent branch without create=True."""
        with pytest.raises(GitError):
            git_ops.checkout_branch("nonexistent")


class TestBranchExists:
    """Tests for branch_exists."""

    def test_true_for_existing_branch(self, temp_git_repo: Path) -> None:
        """Returns True for existing branch."""
        assert git_ops.branch_exists("main") is True

    def test_false_for_nonexistent_branch(self, temp_git_repo: Path) -> None:
        """Returns False for non-existent branch."""
        assert git_ops.branch_exists("nonexistent") is False

    def test_true_after_creating_branch(self, temp_git_repo: Path) -> None:
        """Returns True after creating a branch."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)
        assert git_ops.branch_exists("feature") is True


class TestIsAncestor:
    """Tests for is_ancestor."""

    def test_parent_is_ancestor_of_child(self, temp_git_repo: Path) -> None:
        """Parent commit is ancestor of child commit."""
        # Get initial commit
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
        parent_sha = result.stdout.strip()

        # Create child commit
        Path("file.txt").write_text("content")
        subprocess.run(["git", "add", "file.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "child"], check=True, capture_output=True)

        assert git_ops.is_ancestor(parent_sha, "HEAD") is True

    def test_child_is_not_ancestor_of_parent(self, temp_git_repo: Path) -> None:
        """Child commit is not ancestor of parent commit."""
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
        parent_sha = result.stdout.strip()

        Path("file.txt").write_text("content")
        subprocess.run(["git", "add", "file.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "child"], check=True, capture_output=True)

        assert git_ops.is_ancestor("HEAD", parent_sha) is False

    def test_commit_is_ancestor_of_itself(self, temp_git_repo: Path) -> None:
        """A commit is considered an ancestor of itself."""
        assert git_ops.is_ancestor("HEAD", "HEAD") is True


class TestRebase:
    """Tests for rebase operations."""

    def test_simple_rebase(self, temp_git_repo: Path) -> None:
        """Can rebase one branch onto another."""
        # Create a commit on main
        Path("main_file.txt").write_text("main content")
        subprocess.run(["git", "add", "main_file.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "main commit"], check=True, capture_output=True)

        # Create feature branch from initial commit and add commit
        subprocess.run(
            ["git", "checkout", "-b", "feature", "HEAD~1"], check=True, capture_output=True
        )
        Path("feature_file.txt").write_text("feature content")
        subprocess.run(["git", "add", "feature_file.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature commit"], check=True, capture_output=True)

        # Rebase feature onto main
        git_ops.rebase("main")

        # Verify rebase succeeded - feature should have both files
        assert Path("main_file.txt").exists()
        assert Path("feature_file.txt").exists()

    def test_rebase_onto(self, temp_git_repo: Path) -> None:
        """Can use rebase --onto for complex rebases."""
        # Create: main -> A -> B, then rebase B onto main (skipping A)
        subprocess.run(["git", "checkout", "-b", "branch-a"], check=True, capture_output=True)
        Path("a.txt").write_text("a")
        subprocess.run(["git", "add", "a.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "A"], check=True, capture_output=True)

        subprocess.run(["git", "checkout", "-b", "branch-b"], check=True, capture_output=True)
        Path("b.txt").write_text("b")
        subprocess.run(["git", "add", "b.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "B"], check=True, capture_output=True)

        # Rebase B onto main, removing A's changes
        git_ops.rebase("main", onto="main", upstream="branch-a")

        # B should have b.txt but not a.txt
        assert Path("b.txt").exists()
        assert not Path("a.txt").exists()


class TestIsRebaseInProgress:
    """Tests for is_rebase_in_progress."""

    def test_false_normally(self, temp_git_repo: Path) -> None:
        """Returns False when no rebase is in progress."""
        assert git_ops.is_rebase_in_progress() is False

    def test_true_during_conflict(self, temp_git_repo: Path) -> None:
        """Returns True during a rebase with conflicts."""
        # Create conflicting branches
        Path("conflict.txt").write_text("main content")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "main"], check=True, capture_output=True)

        subprocess.run(
            ["git", "checkout", "-b", "feature", "HEAD~1"], check=True, capture_output=True
        )
        Path("conflict.txt").write_text("feature content")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature"], check=True, capture_output=True)

        # Start rebase (will conflict)
        result = git_ops.rebase("main", check=False)

        if result.returncode != 0:
            assert git_ops.is_rebase_in_progress() is True
            # Cleanup
            subprocess.run(["git", "rebase", "--abort"], check=True, capture_output=True)


class TestRebaseAbort:
    """Tests for rebase_abort."""

    def test_aborts_rebase(self, temp_git_repo: Path) -> None:
        """Can abort an in-progress rebase."""
        # Create conflicting branches
        Path("conflict.txt").write_text("main content")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "main"], check=True, capture_output=True)

        subprocess.run(
            ["git", "checkout", "-b", "feature", "HEAD~1"], check=True, capture_output=True
        )
        Path("conflict.txt").write_text("feature content")
        subprocess.run(["git", "add", "conflict.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature"], check=True, capture_output=True)

        # Start rebase (will conflict)
        git_ops.rebase("main", check=False)

        if git_ops.is_rebase_in_progress():
            git_ops.rebase_abort()
            assert git_ops.is_rebase_in_progress() is False


class TestFetch:
    """Tests for fetch."""

    def test_fetch_from_remote(self, temp_git_repo_with_remote: Path) -> None:
        """Can fetch from remote."""
        git_ops.fetch("origin", "main")
        # Should not raise


class TestPush:
    """Tests for push."""

    def test_push_to_remote(self, temp_git_repo_with_remote: Path) -> None:
        """Can push to remote."""
        # Make a commit
        Path("new.txt").write_text("new content")
        subprocess.run(["git", "add", "new.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "new commit"], check=True, capture_output=True)

        git_ops.push("origin", "main")
        # Should not raise

    def test_push_with_set_upstream(self, temp_git_repo_with_remote: Path) -> None:
        """Can push with -u flag to set upstream."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)
        Path("feature.txt").write_text("feature content")
        subprocess.run(["git", "add", "feature.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature"], check=True, capture_output=True)

        git_ops.push("origin", "feature", set_upstream=True)

        # Verify upstream is set
        result = subprocess.run(
            ["git", "config", "--get", "branch.feature.remote"], capture_output=True, text=True
        )
        assert result.stdout.strip() == "origin"


class TestGetRepoRoot:
    """Tests for get_repo_root."""

    def test_returns_repo_root(self, temp_git_repo: Path) -> None:
        """Returns the repository root path."""
        root = git_ops.get_repo_root()
        assert root == temp_git_repo

    def test_works_from_subdirectory(self, temp_git_repo: Path) -> None:
        """Works when called from a subdirectory."""
        import os

        subdir = temp_git_repo / "subdir"
        subdir.mkdir()
        os.chdir(subdir)

        root = git_ops.get_repo_root()
        assert root == temp_git_repo

    def test_raises_outside_repo(self, tmp_path: Path) -> None:
        """Raises NotAGitRepoError outside a git repository."""
        import os

        original_cwd = os.getcwd()
        os.chdir(tmp_path)

        try:
            with pytest.raises(NotAGitRepoError):
                git_ops.get_repo_root()
        finally:
            os.chdir(original_cwd)


class TestSquashCommits:
    """Tests for squash_commits."""

    def test_squashes_multiple_commits(self, temp_git_repo: Path) -> None:
        """Squashes multiple commits into one."""
        # Create feature branch with multiple commits
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)

        for i in range(3):
            Path(f"file{i}.txt").write_text(f"content {i}")
            subprocess.run(["git", "add", f"file{i}.txt"], check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", f"commit {i}"], check=True, capture_output=True)

        # Count commits before squash
        result = subprocess.run(
            ["git", "rev-list", "--count", "main..feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert int(result.stdout.strip()) == 3

        # Squash
        git_ops.squash_commits("main")

        # Count commits after squash
        result = subprocess.run(
            ["git", "rev-list", "--count", "main..feature"],
            check=True,
            capture_output=True,
            text=True,
        )
        assert int(result.stdout.strip()) == 1

        # Verify all files are still there
        assert Path("file0.txt").exists()
        assert Path("file1.txt").exists()
        assert Path("file2.txt").exists()

    def test_noop_for_single_commit(self, temp_git_repo: Path) -> None:
        """Does nothing if there's only one commit."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)
        Path("file.txt").write_text("content")
        subprocess.run(["git", "add", "file.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "single commit"], check=True, capture_output=True)

        # Get commit SHA before
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
        sha_before = result.stdout.strip()

        # Squash (should be a no-op)
        git_ops.squash_commits("main")

        # Get commit SHA after
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
        sha_after = result.stdout.strip()

        # SHA should be the same (no change)
        assert sha_before == sha_after

    def test_noop_for_no_commits(self, temp_git_repo: Path) -> None:
        """Does nothing if there are no commits since parent."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)

        # Get commit SHA before
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
        sha_before = result.stdout.strip()

        # Squash (should be a no-op)
        git_ops.squash_commits("main")

        # Get commit SHA after
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
        )
        sha_after = result.stdout.strip()

        # SHA should be the same (no change)
        assert sha_before == sha_after

    def test_preserves_first_commit_message(self, temp_git_repo: Path) -> None:
        """Uses the first commit message for the squashed commit."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)

        # First commit with meaningful message
        Path("file1.txt").write_text("content 1")
        subprocess.run(["git", "add", "file1.txt"], check=True, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", "feat: add important feature"],
            check=True,
            capture_output=True,
        )

        # Second commit
        Path("file2.txt").write_text("content 2")
        subprocess.run(["git", "add", "file2.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fix: minor fix"], check=True, capture_output=True)

        git_ops.squash_commits("main")

        # Check commit message
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s"], check=True, capture_output=True, text=True
        )
        assert "feat: add important feature" in result.stdout


class TestDeleteBranch:
    """Tests for delete_branch."""

    def test_deletes_branch(self, temp_git_repo: Path) -> None:
        """Can delete a branch."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        git_ops.delete_branch("feature")
        assert git_ops.branch_exists("feature") is False

    def test_force_deletes_unmerged_branch(self, temp_git_repo: Path) -> None:
        """Can force delete an unmerged branch."""
        subprocess.run(["git", "checkout", "-b", "feature"], check=True, capture_output=True)
        Path("feature.txt").write_text("content")
        subprocess.run(["git", "add", "feature.txt"], check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "feature"], check=True, capture_output=True)
        subprocess.run(["git", "checkout", "main"], check=True, capture_output=True)

        git_ops.delete_branch("feature", force=True)
        assert git_ops.branch_exists("feature") is False
