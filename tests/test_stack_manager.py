"""Tests for stack manager (config and state file operations)."""

import json
from pathlib import Path

import pytest

from gstack import stack_manager
from gstack.models import StackConfig, SyncState


class TestConfigPath:
    """Tests for config file path."""

    def test_config_file_in_repo_root(self, temp_git_repo: Path) -> None:
        """Config file should be at .gstack_config.json in repo root."""
        path = stack_manager.get_config_path(temp_git_repo)
        assert path == temp_git_repo / ".gstack_config.json"


class TestLoadConfig:
    """Tests for loading config."""

    def test_returns_default_when_missing(self, temp_git_repo: Path) -> None:
        """Returns empty StackConfig if file doesn't exist."""
        config = stack_manager.load_config(temp_git_repo)
        assert isinstance(config, StackConfig)
        assert config.branches == {}

    def test_loads_existing_config(self, temp_git_repo: Path) -> None:
        """Loads config from existing file."""
        config_path = temp_git_repo / ".gstack_config.json"
        config_data = {
            "trunk": "main",
            "branches": {
                "feature": {"parent": "main", "children": [], "pr_url": None}
            }
        }
        config_path.write_text(json.dumps(config_data))

        config = stack_manager.load_config(temp_git_repo)
        assert config.trunk == "main"
        assert "feature" in config.branches
        assert config.branches["feature"].parent == "main"

    def test_handles_corrupted_json(self, temp_git_repo: Path) -> None:
        """Raises error for corrupted JSON."""
        config_path = temp_git_repo / ".gstack_config.json"
        config_path.write_text("{ invalid json }")

        with pytest.raises(stack_manager.ConfigError):
            stack_manager.load_config(temp_git_repo)


class TestSaveConfig:
    """Tests for saving config."""

    def test_creates_config_file(self, temp_git_repo: Path) -> None:
        """Creates config file if it doesn't exist."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")

        stack_manager.save_config(config, temp_git_repo)

        config_path = temp_git_repo / ".gstack_config.json"
        assert config_path.exists()

    def test_save_and_load_roundtrip(self, temp_git_repo: Path) -> None:
        """Config survives write/read cycle."""
        config = StackConfig(trunk="main")
        config.add_branch("feature", parent="main")
        config.add_branch("feature-ui", parent="feature")
        config.branches["feature"].pr_url = "https://github.com/org/repo/pull/1"

        stack_manager.save_config(config, temp_git_repo)
        loaded = stack_manager.load_config(temp_git_repo)

        assert loaded.trunk == config.trunk
        assert loaded.branches == config.branches

    def test_overwrites_existing_config(self, temp_git_repo: Path) -> None:
        """Overwrites existing config file."""
        config1 = StackConfig(trunk="main")
        config1.add_branch("old-feature", parent="main")
        stack_manager.save_config(config1, temp_git_repo)

        config2 = StackConfig(trunk="main")
        config2.add_branch("new-feature", parent="main")
        stack_manager.save_config(config2, temp_git_repo)

        loaded = stack_manager.load_config(temp_git_repo)
        assert "new-feature" in loaded.branches
        assert "old-feature" not in loaded.branches


class TestInitConfig:
    """Tests for initializing config."""

    def test_creates_new_config(self, temp_git_repo: Path) -> None:
        """Creates a new config file."""
        stack_manager.init_config(temp_git_repo)

        config_path = temp_git_repo / ".gstack_config.json"
        assert config_path.exists()

    def test_auto_detects_trunk(self, temp_git_repo: Path) -> None:
        """Uses git_ops.detect_trunk() for initial trunk value."""
        stack_manager.init_config(temp_git_repo)

        config = stack_manager.load_config(temp_git_repo)
        assert config.trunk == "main"  # temp_git_repo uses main

    def test_uses_explicit_trunk(self, temp_git_repo: Path) -> None:
        """Uses explicit trunk if provided."""
        stack_manager.init_config(temp_git_repo, trunk="develop")

        config = stack_manager.load_config(temp_git_repo)
        assert config.trunk == "develop"

    def test_raises_if_already_initialized(self, temp_git_repo: Path) -> None:
        """Raises error if config already exists."""
        stack_manager.init_config(temp_git_repo)

        with pytest.raises(stack_manager.AlreadyInitializedError):
            stack_manager.init_config(temp_git_repo)

    def test_force_reinitializes(self, temp_git_repo: Path) -> None:
        """Can force reinitialize with force=True."""
        stack_manager.init_config(temp_git_repo)
        config = stack_manager.load_config(temp_git_repo)
        config.add_branch("feature", parent="main")
        stack_manager.save_config(config, temp_git_repo)

        stack_manager.init_config(temp_git_repo, force=True)

        config = stack_manager.load_config(temp_git_repo)
        assert config.branches == {}


class TestIsInitialized:
    """Tests for checking if gstack is initialized."""

    def test_false_when_no_config(self, temp_git_repo: Path) -> None:
        """Returns False when config doesn't exist."""
        assert stack_manager.is_initialized(temp_git_repo) is False

    def test_true_when_config_exists(self, temp_git_repo: Path) -> None:
        """Returns True when config exists."""
        stack_manager.init_config(temp_git_repo)
        assert stack_manager.is_initialized(temp_git_repo) is True


class TestRequireInitialized:
    """Tests for requiring initialization."""

    def test_passes_when_initialized(self, temp_git_repo: Path) -> None:
        """Does not raise when initialized."""
        stack_manager.init_config(temp_git_repo)
        stack_manager.require_initialized(temp_git_repo)  # Should not raise

    def test_raises_when_not_initialized(self, temp_git_repo: Path) -> None:
        """Raises NotInitializedError when not initialized."""
        from gstack.exceptions import NotInitializedError
        with pytest.raises(NotInitializedError):
            stack_manager.require_initialized(temp_git_repo)


class TestStatePath:
    """Tests for state file path."""

    def test_state_file_in_git_dir(self, temp_git_repo: Path) -> None:
        """State file should be at .git/.gstack_state.json."""
        path = stack_manager.get_state_path(temp_git_repo)
        assert path == temp_git_repo / ".git" / ".gstack_state.json"


class TestLoadState:
    """Tests for loading state."""

    def test_returns_none_when_missing(self, temp_git_repo: Path) -> None:
        """Returns None if state file doesn't exist."""
        state = stack_manager.load_state(temp_git_repo)
        assert state is None

    def test_loads_existing_state(self, temp_git_repo: Path) -> None:
        """Loads state from existing file."""
        state_path = temp_git_repo / ".git" / ".gstack_state.json"
        state_data = {
            "active_command": "sync",
            "todo_queue": ["feature", "feature-ui"],
            "current_index": 1,
            "original_head": "feature-ui"
        }
        state_path.write_text(json.dumps(state_data))

        state = stack_manager.load_state(temp_git_repo)
        assert state is not None
        assert state.active_command == "sync"
        assert state.todo_queue == ["feature", "feature-ui"]
        assert state.current_index == 1


class TestSaveState:
    """Tests for saving state."""

    def test_creates_state_file(self, temp_git_repo: Path) -> None:
        """Creates state file."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature"],
            original_head="feature"
        )

        stack_manager.save_state(state, temp_git_repo)

        state_path = temp_git_repo / ".git" / ".gstack_state.json"
        assert state_path.exists()

    def test_save_and_load_roundtrip(self, temp_git_repo: Path) -> None:
        """State survives write/read cycle."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature", "feature-ui"],
            current_index=1,
            original_head="feature-ui"
        )

        stack_manager.save_state(state, temp_git_repo)
        loaded = stack_manager.load_state(temp_git_repo)

        assert loaded is not None
        assert loaded == state


class TestClearState:
    """Tests for clearing state."""

    def test_removes_state_file(self, temp_git_repo: Path) -> None:
        """Removes state file."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature"],
            original_head="feature"
        )
        stack_manager.save_state(state, temp_git_repo)

        stack_manager.clear_state(temp_git_repo)

        state_path = temp_git_repo / ".git" / ".gstack_state.json"
        assert not state_path.exists()

    def test_no_error_when_no_state(self, temp_git_repo: Path) -> None:
        """No error when state file doesn't exist."""
        stack_manager.clear_state(temp_git_repo)  # Should not raise


class TestHasPendingState:
    """Tests for checking pending state."""

    def test_false_when_no_state(self, temp_git_repo: Path) -> None:
        """Returns False when no state file exists."""
        assert stack_manager.has_pending_state(temp_git_repo) is False

    def test_true_when_state_exists(self, temp_git_repo: Path) -> None:
        """Returns True when state file exists."""
        state = SyncState(
            active_command="sync",
            todo_queue=["feature"],
            original_head="feature"
        )
        stack_manager.save_state(state, temp_git_repo)

        assert stack_manager.has_pending_state(temp_git_repo) is True


class TestRegisterBranch:
    """Tests for registering a new branch."""

    def test_adds_branch_to_config(self, temp_git_repo: Path) -> None:
        """Adds branch to config and saves."""
        stack_manager.init_config(temp_git_repo)

        stack_manager.register_branch("feature", parent="main", repo_root=temp_git_repo)

        config = stack_manager.load_config(temp_git_repo)
        assert "feature" in config.branches
        assert config.branches["feature"].parent == "main"

    def test_updates_parent_children(self, temp_git_repo: Path) -> None:
        """Updates parent's children list."""
        stack_manager.init_config(temp_git_repo)
        stack_manager.register_branch("feature", parent="main", repo_root=temp_git_repo)

        stack_manager.register_branch("feature-ui", parent="feature", repo_root=temp_git_repo)

        config = stack_manager.load_config(temp_git_repo)
        assert "feature-ui" in config.branches["feature"].children


class TestUnregisterBranch:
    """Tests for unregistering a branch."""

    def test_removes_branch_from_config(self, temp_git_repo: Path) -> None:
        """Removes branch from config."""
        stack_manager.init_config(temp_git_repo)
        stack_manager.register_branch("feature", parent="main", repo_root=temp_git_repo)

        stack_manager.unregister_branch("feature", repo_root=temp_git_repo)

        config = stack_manager.load_config(temp_git_repo)
        assert "feature" not in config.branches

    def test_reparents_children(self, temp_git_repo: Path) -> None:
        """Reparents children to grandparent."""
        stack_manager.init_config(temp_git_repo)
        stack_manager.register_branch("feature", parent="main", repo_root=temp_git_repo)
        stack_manager.register_branch("feature-ui", parent="feature", repo_root=temp_git_repo)

        stack_manager.unregister_branch("feature", repo_root=temp_git_repo)

        config = stack_manager.load_config(temp_git_repo)
        assert "feature" not in config.branches
        assert config.branches["feature-ui"].parent == "main"
