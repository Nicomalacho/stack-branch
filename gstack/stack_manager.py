"""Stack manager for gstack configuration and state persistence.

Handles reading/writing the config file (.gstack_config.json) and
state file (.git/.gstack_state.json).
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from gstack import git_ops
from gstack.exceptions import NotInitializedError
from gstack.models import StackConfig, SyncState


class ConfigError(Exception):
    """Error reading or parsing config file."""

    pass


class AlreadyInitializedError(Exception):
    """gstack is already initialized in this repository."""

    pass


CONFIG_FILENAME = ".gstack_config.json"
STATE_FILENAME = ".gstack_state.json"


def get_config_path(repo_root: Path) -> Path:
    """Get the path to the config file.

    Args:
        repo_root: Repository root directory.

    Returns:
        Path to .gstack_config.json.
    """
    return repo_root / CONFIG_FILENAME


def get_state_path(repo_root: Path) -> Path:
    """Get the path to the state file.

    Args:
        repo_root: Repository root directory.

    Returns:
        Path to .git/.gstack_state.json.
    """
    return repo_root / ".git" / STATE_FILENAME


def load_config(repo_root: Path) -> StackConfig:
    """Load the stack config from disk.

    Args:
        repo_root: Repository root directory.

    Returns:
        StackConfig loaded from file, or default empty config if file doesn't exist.

    Raises:
        ConfigError: If the config file exists but is invalid.
    """
    config_path = get_config_path(repo_root)

    if not config_path.exists():
        return StackConfig()

    try:
        content = config_path.read_text()
        return StackConfig.model_validate_json(content)
    except json.JSONDecodeError as e:
        raise ConfigError(f"Invalid JSON in config file: {e}") from e
    except ValidationError as e:
        raise ConfigError(f"Invalid config format: {e}") from e


def save_config(config: StackConfig, repo_root: Path) -> None:
    """Save the stack config to disk.

    Args:
        config: StackConfig to save.
        repo_root: Repository root directory.
    """
    config_path = get_config_path(repo_root)
    config_path.write_text(config.model_dump_json(indent=2))


def init_config(
    repo_root: Path,
    trunk: str | None = None,
    force: bool = False,
) -> StackConfig:
    """Initialize gstack in a repository.

    Args:
        repo_root: Repository root directory.
        trunk: Trunk branch name. If None, auto-detected.
        force: If True, reinitialize even if already initialized.

    Returns:
        The newly created StackConfig.

    Raises:
        AlreadyInitializedError: If already initialized and force=False.
    """
    config_path = get_config_path(repo_root)

    if config_path.exists() and not force:
        raise AlreadyInitializedError("gstack is already initialized. Use --force to reinitialize.")

    # Auto-detect trunk if not specified
    if trunk is None:
        trunk = git_ops.detect_trunk()

    config = StackConfig(trunk=trunk)
    save_config(config, repo_root)

    return config


def is_initialized(repo_root: Path) -> bool:
    """Check if gstack is initialized in a repository.

    Args:
        repo_root: Repository root directory.

    Returns:
        True if config file exists.
    """
    return get_config_path(repo_root).exists()


def require_initialized(repo_root: Path) -> None:
    """Require gstack to be initialized.

    Args:
        repo_root: Repository root directory.

    Raises:
        NotInitializedError: If not initialized.
    """
    if not is_initialized(repo_root):
        raise NotInitializedError()


def load_state(repo_root: Path) -> SyncState | None:
    """Load the sync state from disk.

    Args:
        repo_root: Repository root directory.

    Returns:
        SyncState if file exists, None otherwise.
    """
    state_path = get_state_path(repo_root)

    if not state_path.exists():
        return None

    content = state_path.read_text()
    return SyncState.model_validate_json(content)


def save_state(state: SyncState, repo_root: Path) -> None:
    """Save the sync state to disk.

    Args:
        state: SyncState to save.
        repo_root: Repository root directory.
    """
    state_path = get_state_path(repo_root)
    state_path.write_text(state.model_dump_json(indent=2))


def clear_state(repo_root: Path) -> None:
    """Clear the sync state (delete state file).

    Args:
        repo_root: Repository root directory.
    """
    state_path = get_state_path(repo_root)

    if state_path.exists():
        state_path.unlink()


def has_pending_state(repo_root: Path) -> bool:
    """Check if there's a pending sync/submit operation.

    Args:
        repo_root: Repository root directory.

    Returns:
        True if state file exists.
    """
    return get_state_path(repo_root).exists()


def register_branch(name: str, parent: str, repo_root: Path) -> None:
    """Register a new branch in the stack.

    Args:
        name: Branch name to register.
        parent: Parent branch name.
        repo_root: Repository root directory.
    """
    config = load_config(repo_root)
    config.add_branch(name, parent)
    save_config(config, repo_root)


def unregister_branch(name: str, repo_root: Path) -> None:
    """Unregister a branch from the stack.

    Children are automatically reparented to the grandparent.

    Args:
        name: Branch name to unregister.
        repo_root: Repository root directory.
    """
    config = load_config(repo_root)
    config.remove_branch(name)
    save_config(config, repo_root)
