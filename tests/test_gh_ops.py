"""Tests for GitHub CLI operations wrapper."""

import json
import subprocess

import pytest

from gstack import gh_ops
from gstack.exceptions import GhError, GhNotAuthenticatedError


class TestRunGh:
    """Tests for the run_gh wrapper function."""

    def test_captures_stdout(self, mocker) -> None:
        """Output is captured correctly."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "auth", "status"],
            returncode=0,
            stdout="Logged in to github.com",
            stderr="",
        )

        result = gh_ops.run_gh("auth", "status")
        assert result.stdout == "Logged in to github.com"

    def test_raises_on_failure(self, mocker) -> None:
        """GhError raised on non-zero exit."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=1,
            stdout="",
            stderr="no pull request found",
        )

        with pytest.raises(GhError):
            gh_ops.run_gh("pr", "view")

    def test_check_false_does_not_raise(self, mocker) -> None:
        """With check=False, no exception is raised on failure."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=1,
            stdout="",
            stderr="no pull request found",
        )

        result = gh_ops.run_gh("pr", "view", check=False)
        assert result.returncode == 1


class TestIsGhAuthenticated:
    """Tests for is_gh_authenticated."""

    def test_returns_true_when_authenticated(self, mocker) -> None:
        """Returns True when gh auth status succeeds."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "auth", "status"],
            returncode=0,
            stdout="Logged in to github.com as user",
            stderr="",
        )

        assert gh_ops.is_gh_authenticated() is True

    def test_returns_false_when_not_authenticated(self, mocker) -> None:
        """Returns False when gh auth status fails."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "auth", "status"],
            returncode=1,
            stdout="",
            stderr="You are not logged in",
        )

        assert gh_ops.is_gh_authenticated() is False


class TestGetPrInfo:
    """Tests for get_pr_info."""

    def test_returns_pr_info(self, mocker) -> None:
        """Returns PR info when PR exists."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=0,
            stdout=json.dumps(
                {
                    "url": "https://github.com/org/repo/pull/1",
                    "baseRefName": "main",
                    "state": "OPEN",
                    "number": 1,
                }
            ),
            stderr="",
        )

        info = gh_ops.get_pr_info("feature")

        assert info is not None
        assert info.url == "https://github.com/org/repo/pull/1"
        assert info.base == "main"
        assert info.state == "OPEN"
        assert info.number == 1

    def test_returns_none_when_no_pr(self, mocker) -> None:
        """Returns None when PR doesn't exist."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=1,
            stdout="",
            stderr="no pull requests found for branch",
        )

        info = gh_ops.get_pr_info("feature")
        assert info is None


class TestCreatePr:
    """Tests for create_pr."""

    def test_creates_pr(self, mocker) -> None:
        """Creates PR with correct arguments."""
        mock_run = mocker.patch("subprocess.run")
        # gh pr create outputs the URL directly, not JSON
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/org/repo/pull/1\n",
            stderr="",
        )

        result = gh_ops.create_pr(
            head="feature",
            base="main",
            title="Add feature",
            body="Description",
        )

        assert result.url == "https://github.com/org/repo/pull/1"
        assert result.number == 1
        # Verify the command was called correctly
        call_args = mock_run.call_args[0][0]
        assert "pr" in call_args
        assert "create" in call_args
        assert "--head" in call_args
        assert "feature" in call_args
        assert "--base" in call_args
        assert "main" in call_args
        # Should NOT have --json flag
        assert "--json" not in call_args

    def test_creates_pr_with_defaults(self, mocker) -> None:
        """Creates PR with default title/body."""
        mock_run = mocker.patch("subprocess.run")
        # gh pr create outputs the URL directly, not JSON
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
<<<<<<< HEAD
            stdout="https://github.com/org/repo/pull/1\n",
=======
            stdout="https://github.com/org/repo/pull/42\n",
>>>>>>> 6c6a2f3 (Some fixes)
            stderr="",
        )

        result = gh_ops.create_pr(head="feature", base="main")
        assert result.url == "https://github.com/org/repo/pull/42"
        assert result.number == 42

    def test_does_not_use_json_flag(self, mocker) -> None:
        """gh pr create does not support --json flag."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/org/repo/pull/42\n",
            stderr="",
        )

        gh_ops.create_pr(head="feature", base="main")

        # Verify --json is NOT in the command args
        call_args = mock_run.call_args[0][0]
        assert "--json" not in call_args, "gh pr create does not support --json flag"

    def test_extracts_pr_number_from_url(self, mocker) -> None:
        """PR number is extracted from the URL."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "create"],
            returncode=0,
            stdout="https://github.com/org/repo/pull/42\n",
            stderr="",
        )

        result = gh_ops.create_pr(head="feature", base="main")

        assert result.number == 42
        assert result.url == "https://github.com/org/repo/pull/42"


class TestUpdatePrBase:
    """Tests for update_pr_base."""

    def test_updates_pr_base(self, mocker) -> None:
        """Updates PR base branch."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "edit"],
            returncode=0,
            stdout="",
            stderr="",
        )

        gh_ops.update_pr_base("feature", new_base="develop")

        call_args = mock_run.call_args[0][0]
        assert "pr" in call_args
        assert "edit" in call_args
        assert "--base" in call_args
        assert "develop" in call_args


class TestIsPrMerged:
    """Tests for is_pr_merged."""

    def test_returns_true_when_merged(self, mocker) -> None:
        """Returns True when PR state is MERGED."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=0,
            stdout=json.dumps(
                {
                    "url": "https://github.com/org/repo/pull/1",
                    "baseRefName": "main",
                    "state": "MERGED",
                    "number": 1,
                }
            ),
            stderr="",
        )

        assert gh_ops.is_pr_merged("feature") is True

    def test_returns_false_when_open(self, mocker) -> None:
        """Returns False when PR state is OPEN."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=0,
            stdout=json.dumps(
                {
                    "url": "https://github.com/org/repo/pull/1",
                    "baseRefName": "main",
                    "state": "OPEN",
                    "number": 1,
                }
            ),
            stderr="",
        )

        assert gh_ops.is_pr_merged("feature") is False

    def test_returns_false_when_no_pr(self, mocker) -> None:
        """Returns False when no PR exists."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "pr", "view"],
            returncode=1,
            stdout="",
            stderr="no pull requests found",
        )

        assert gh_ops.is_pr_merged("feature") is False


class TestRequireGhAuth:
    """Tests for require_gh_auth."""

    def test_passes_when_authenticated(self, mocker) -> None:
        """Does not raise when authenticated."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "auth", "status"],
            returncode=0,
            stdout="Logged in",
            stderr="",
        )

        gh_ops.require_gh_auth()  # Should not raise

    def test_raises_when_not_authenticated(self, mocker) -> None:
        """Raises GhNotAuthenticatedError when not authenticated."""
        mock_run = mocker.patch("subprocess.run")
        mock_run.return_value = subprocess.CompletedProcess(
            args=["gh", "auth", "status"],
            returncode=1,
            stdout="",
            stderr="You are not logged in",
        )

        with pytest.raises(GhNotAuthenticatedError):
            gh_ops.require_gh_auth()


class TestGenerateStackMermaid:
    """Tests for generate_stack_mermaid."""

    def test_generates_basic_diagram(self) -> None:
        """Generates a valid mermaid diagram."""
        from gstack.models import BranchInfo

        branches = {
            "feature": BranchInfo(parent="main", children=["feature-ui"]),
            "feature-ui": BranchInfo(parent="feature", children=[]),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main")

        assert "```mermaid" in diagram
        assert "graph TD" in diagram
        assert "main[main]" in diagram
        assert "feature" in diagram
        assert "feature-ui" in diagram
        assert "main --> feature" in diagram
        assert "feature --> feature-ui" in diagram

    def test_includes_pr_links(self) -> None:
        """Includes PR links in node labels."""
        from gstack.models import BranchInfo

        branches = {
            "feature": BranchInfo(
                parent="main",
                children=[],
                pr_url="https://github.com/org/repo/pull/42",
            ),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main")

        assert "##42" in diagram  # PR number in label
        assert "https://github.com/org/repo/pull/42" in diagram

    def test_highlights_current_branch(self) -> None:
        """Highlights the current branch."""
        from gstack.models import BranchInfo

        branches = {
            "feature": BranchInfo(parent="main", children=[]),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main", current_branch="feature")

        assert "style feature fill:#90EE90" in diagram

    def test_includes_marker(self) -> None:
        """Includes the gstack marker for updates."""
        from gstack.models import BranchInfo

        branches = {
            "feature": BranchInfo(parent="main", children=[]),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main")

        assert gh_ops.STACK_COMMENT_MARKER in diagram

    def test_no_html_in_mermaid_nodes(self) -> None:
        """Mermaid nodes should not contain raw HTML tags that break parsing."""
        from gstack.models import BranchInfo

        branches = {
            "feature": BranchInfo(
                parent="main",
                children=[],
                pr_url="https://github.com/org/repo/pull/42",
            ),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main")

        # Should NOT contain HTML <a> tags inside node definitions
        # These break GitHub's mermaid parser
        assert "<a href=" not in diagram
        assert "</a>" not in diagram

    def test_uses_click_directive_for_links(self) -> None:
        """PR links should use mermaid click directive, not HTML."""
        from gstack.models import BranchInfo

        branches = {
            "feature": BranchInfo(
                parent="main",
                children=[],
                pr_url="https://github.com/org/repo/pull/42",
            ),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main")

        # Should use mermaid's click directive for clickable nodes
        assert "click feature" in diagram
        assert "https://github.com/org/repo/pull/42" in diagram

    def test_valid_mermaid_syntax(self) -> None:
        """Generated mermaid should have valid syntax structure."""
        from gstack.models import BranchInfo

        branches = {
            "feature": BranchInfo(
                parent="main",
                children=["feature-ui"],
                pr_url="https://github.com/org/repo/pull/1",
            ),
            "feature-ui": BranchInfo(
                parent="feature",
                children=[],
                pr_url="https://github.com/org/repo/pull/2",
            ),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main", current_branch="feature")

        # Basic structure checks
        assert diagram.startswith("<!-- gstack-diagram -->")
        assert "```mermaid" in diagram
        assert "```" in diagram  # closing fence

    def test_no_nested_brackets_in_labels(self) -> None:
        """Mermaid labels must not have nested brackets like name[label [#6]]."""
        from gstack.models import BranchInfo

        branches = {
            "feat_move_command": BranchInfo(
                parent="main",
                children=[],
                pr_url="https://github.com/org/repo/pull/6",
            ),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main")

        # Should NOT have nested brackets like: name[label [#6]]
        # This causes mermaid parse error: Expecting 'SQE', got 'SQS'
        assert "[#" not in diagram, "Nested brackets [#n] break mermaid parsing"

        # Should use quoted labels instead: name["label #6"]
        assert '["' in diagram or "[" in diagram

    def test_pr_label_uses_quoted_syntax(self) -> None:
        """PR labels should use quoted mermaid syntax to avoid bracket issues."""
        from gstack.models import BranchInfo

        branches = {
            "feature": BranchInfo(
                parent="main",
                children=[],
                pr_url="https://github.com/org/repo/pull/42",
            ),
        }

        diagram = gh_ops.generate_stack_mermaid(branches, "main")

        # Valid mermaid: feature["feature #42"]
        # Invalid mermaid: feature[feature [#42]]
        lines = diagram.split("\n")
        for line in lines:
            # Check node definition lines (contain branch name and brackets)
            if "feature[" in line and "#42" in line:
                # Should be quoted: feature["..."]
                assert '["' in line, f"Label should use quotes: {line}"
                # Should NOT have nested unquoted brackets
                assert "[#" not in line, f"Nested brackets break mermaid: {line}"
