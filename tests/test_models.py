"""Tests for gstack data models."""

import pytest

from gstack.models import BranchInfo, StackConfig, SyncState


class TestBranchInfo:
    """Tests for BranchInfo model."""

    def test_defaults(self) -> None:
        """BranchInfo should have empty children and no PR by default."""
        info = BranchInfo(parent="main")
        assert info.parent == "main"
        assert info.children == []
        assert info.pr_url is None

    def test_with_children(self) -> None:
        """BranchInfo can have children."""
        info = BranchInfo(parent="main", children=["feature-ui", "feature-api"])
        assert info.children == ["feature-ui", "feature-api"]

    def test_with_pr_url(self) -> None:
        """BranchInfo can store PR URL."""
        info = BranchInfo(parent="main", pr_url="https://github.com/org/repo/pull/1")
        assert info.pr_url == "https://github.com/org/repo/pull/1"

    def test_serialization(self) -> None:
        """BranchInfo survives JSON round-trip."""
        info = BranchInfo(parent="main", children=["child"], pr_url="https://example.com")
        data = info.model_dump()
        restored = BranchInfo(**data)
        assert restored == info


class TestStackConfig:
    """Tests for StackConfig model."""

    def test_defaults(self) -> None:
        """StackConfig has sensible defaults."""
        config = StackConfig()
        assert config.trunk == "main"
        assert config.branches == {}

    def test_add_branch(self) -> None:
        """Adding a branch updates parent's children list."""
        config = StackConfig(trunk="main")
        config.add_branch("feature-login", parent="main")

        assert "feature-login" in config.branches
        assert config.branches["feature-login"].parent == "main"

    def test_add_branch_updates_parent_children(self) -> None:
        """Adding a branch adds it to parent's children list."""
        config = StackConfig(trunk="main")
        config.add_branch("feature-login", parent="main")
        config.add_branch("feature-login-ui", parent="feature-login")

        assert "feature-login-ui" in config.branches["feature-login"].children

    def test_add_branch_trunk_not_in_branches(self) -> None:
        """Trunk branch is not added to branches dict."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")

        assert "main" not in config.branches
        assert "feature" in config.branches

    def test_remove_branch_reparents_children(self) -> None:
        """Deleting branch reparents children to grandparent."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-ui", parent="feature")
        config.add_branch("feature-api", parent="feature")

        config.remove_branch("feature")

        # Children should now point to grandparent (main)
        assert config.branches["feature-ui"].parent == "main"
        assert config.branches["feature-api"].parent == "main"
        assert "feature" not in config.branches

    def test_remove_branch_updates_grandparent_children(self) -> None:
        """Removing a branch updates grandparent's children list."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-ui", parent="feature")

        config.remove_branch("feature")

        # Grandparent (main) is trunk, so we check the orphaned children are reparented
        assert config.branches["feature-ui"].parent == "main"

    def test_remove_leaf_branch(self) -> None:
        """Removing a leaf branch with no children works."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-ui", parent="feature")

        config.remove_branch("feature-ui")

        assert "feature-ui" not in config.branches
        assert "feature-ui" not in config.branches["feature"].children

    def test_get_stack_returns_path_to_trunk(self) -> None:
        """get_stack returns path from trunk to branch."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-ui", parent="feature")
        config.add_branch("feature-ui-button", parent="feature-ui")

        stack = config.get_stack("feature-ui-button")

        assert stack == ["main", "feature", "feature-ui", "feature-ui-button"]

    def test_get_stack_single_branch(self) -> None:
        """get_stack works for branch directly off trunk."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")

        stack = config.get_stack("feature")

        assert stack == ["main", "feature"]

    def test_get_stack_trunk_returns_just_trunk(self) -> None:
        """get_stack for trunk returns just trunk."""
        config = StackConfig(trunk="main")

        stack = config.get_stack("main")

        assert stack == ["main"]

    def test_get_descendants(self) -> None:
        """get_descendants returns all children recursively."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-ui", parent="feature")
        config.add_branch("feature-api", parent="feature")
        config.add_branch("feature-ui-button", parent="feature-ui")

        descendants = config.get_descendants("feature")

        assert set(descendants) == {"feature-ui", "feature-api", "feature-ui-button"}

    def test_get_descendants_leaf_returns_empty(self) -> None:
        """get_descendants for leaf branch returns empty list."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")

        descendants = config.get_descendants("feature")

        assert descendants == []

    def test_topological_sort(self) -> None:
        """Topological sort returns parents before children."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-ui", parent="feature")
        config.add_branch("feature-api", parent="feature")
        config.add_branch("feature-ui-button", parent="feature-ui")

        # Sort all branches
        branches = ["feature-ui-button", "feature-api", "feature-ui", "feature"]
        sorted_branches = config.topological_sort(branches)

        # feature must come before feature-ui and feature-api
        assert sorted_branches.index("feature") < sorted_branches.index("feature-ui")
        assert sorted_branches.index("feature") < sorted_branches.index("feature-api")
        # feature-ui must come before feature-ui-button
        assert sorted_branches.index("feature-ui") < sorted_branches.index("feature-ui-button")

    def test_topological_sort_preserves_order_for_siblings(self) -> None:
        """Siblings maintain stable order in topological sort."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-a", parent="feature")
        config.add_branch("feature-b", parent="feature")
        config.add_branch("feature-c", parent="feature")

        branches = ["feature", "feature-a", "feature-b", "feature-c"]
        sorted_branches = config.topological_sort(branches)

        # feature must be first, siblings can be in any order after
        assert sorted_branches[0] == "feature"

    def test_isolated_stacks(self) -> None:
        """Branches with different roots are separate stacks."""
        config = StackConfig(trunk="main")
        # Stack 1
        config.add_branch("feature-auth", parent="main")
        config.add_branch("feature-auth-ui", parent="feature-auth")
        # Stack 2
        config.add_branch("feature-payments", parent="main")
        config.add_branch("feature-payments-api", parent="feature-payments")

        # Each stack is independent
        auth_descendants = config.get_descendants("feature-auth")
        payments_descendants = config.get_descendants("feature-payments")

        assert set(auth_descendants) == {"feature-auth-ui"}
        assert set(payments_descendants) == {"feature-payments-api"}

    def test_serialization(self) -> None:
        """StackConfig survives JSON round-trip."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-ui", parent="feature")

        json_str = config.model_dump_json()
        restored = StackConfig.model_validate_json(json_str)

        assert restored.trunk == config.trunk
        assert restored.branches == config.branches

    def test_branch_not_found_error(self) -> None:
        """Operations on non-existent branches raise KeyError."""
        config = StackConfig(trunk="main")

        with pytest.raises(KeyError):
            config.get_stack("nonexistent")

    def test_remove_nonexistent_branch_raises(self) -> None:
        """Removing non-existent branch raises KeyError."""
        config = StackConfig(trunk="main")

        with pytest.raises(KeyError):
            config.remove_branch("nonexistent")


class TestSyncState:
    """Tests for SyncState model."""

    def test_creation(self) -> None:
        """SyncState can be created with required fields."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature", "feature-ui"],
            original_head="feature-ui",
        )
        assert state.active_command == "sync"
        assert state.todo_queue == ["feature", "feature-ui"]
        assert state.current_index == 0
        assert state.original_head == "feature-ui"

    def test_current_index_default(self) -> None:
        """current_index defaults to 0."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature"],
            original_head="feature",
        )
        assert state.current_index == 0

    def test_active_command_validation(self) -> None:
        """active_command must be 'sync' or 'submit'."""
        # Valid values
        SyncState(active_command="sync", todo_queue=[], original_head="main")
        SyncState(active_command="submit", todo_queue=[], original_head="main")

        # Invalid value
        with pytest.raises(ValueError):
            SyncState(active_command="invalid", todo_queue=[], original_head="main")

    def test_serialization(self) -> None:
        """SyncState survives JSON round-trip."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature", "feature-ui"],
            current_index=1,
            original_head="feature-ui",
        )

        json_str = state.model_dump_json()
        restored = SyncState.model_validate_json(json_str)

        assert restored == state

    def test_current_branch_property(self) -> None:
        """current_branch returns the branch at current_index."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature", "feature-ui", "feature-api"],
            current_index=1,
            original_head="feature-api",
        )
        assert state.current_branch == "feature-ui"

    def test_current_branch_none_when_done(self) -> None:
        """current_branch returns None when index is past the queue."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature"],
            current_index=1,
            original_head="feature",
        )
        assert state.current_branch is None

    def test_is_complete(self) -> None:
        """is_complete returns True when all items processed."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature", "feature-ui"],
            current_index=2,
            original_head="feature-ui",
        )
        assert state.is_complete is True

    def test_is_not_complete(self) -> None:
        """is_complete returns False when items remain."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature", "feature-ui"],
            current_index=1,
            original_head="feature-ui",
        )
        assert state.is_complete is False
