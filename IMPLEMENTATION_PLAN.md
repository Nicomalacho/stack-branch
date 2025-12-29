# gstack Implementation Plan

> **Approach**: Test-Driven Development (TDD) - write tests first, then implement

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Trunk detection | Auto-detect (main → master) | Better UX, no manual config needed |
| Stack isolation | Isolated stacks | Each stack independent, cleaner mental model |
| Branch deletion | Auto-reparent children | Less friction, grandparent becomes new parent |
| Upstream tracking | Auto-track on push | Simplify workflow, -u on first push |

---

## Phase 1: Project Setup & Test Infrastructure

### 1.1 Project Structure
```
gstack/
├── pyproject.toml
├── gstack/
│   ├── __init__.py
│   ├── main.py             # CLI entry point (typer)
│   ├── git_ops.py          # Git subprocess wrapper
│   ├── gh_ops.py           # GitHub CLI wrapper
│   ├── stack_manager.py    # Config file management
│   ├── workflow_engine.py  # Sync/Submit orchestration
│   ├── models.py           # Pydantic data models
│   └── exceptions.py       # Custom exceptions
└── tests/
    ├── __init__.py
    ├── conftest.py         # Shared fixtures (temp git repos, mocks)
    ├── test_models.py
    ├── test_git_ops.py
    ├── test_stack_manager.py
    ├── test_gh_ops.py
    ├── test_workflow_engine.py
    └── test_cli.py
```

### 1.2 Dependencies
```toml
[project]
dependencies = [
    "typer[all]>=0.9.0",
    "pydantic>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-cov",
    "pytest-mock",
]

[project.scripts]
gstack = "gstack.main:app"
```

### 1.3 Test Fixtures (`conftest.py`)
```python
@pytest.fixture
def temp_git_repo(tmp_path):
    """Create a temporary git repo with initial commit."""
    # git init, create main branch, initial commit

@pytest.fixture
def mock_subprocess(mocker):
    """Mock subprocess.run for git/gh commands."""
```

### 1.4 Deliverables
- [ ] Initialize pyproject.toml with deps
- [ ] Create conftest.py with temp_git_repo fixture
- [ ] Verify `pytest` runs (0 tests initially)

---

## Phase 2: Data Models (`models.py`)

### 2.1 Tests First (`test_models.py`)
```python
def test_branch_info_defaults():
    """BranchInfo should have empty children and no PR by default."""

def test_stack_config_add_branch():
    """Adding a branch updates parent's children list."""

def test_stack_config_isolated_stacks():
    """Branches with different roots are separate stacks."""

def test_stack_config_get_stack_returns_path_to_trunk():
    """get_stack('feature-ui') returns ['main', 'feature', 'feature-ui']."""

def test_stack_config_topological_sort():
    """Sort returns parents before children."""

def test_stack_config_reparent_on_delete():
    """Deleting branch reparents children to grandparent."""

def test_sync_state_serialization():
    """State survives round-trip to JSON."""
```

### 2.2 Implementation
```python
class BranchInfo(BaseModel):
    parent: str
    children: list[str] = []
    pr_url: str | None = None

class StackConfig(BaseModel):
    trunk: str = "main"
    branches: dict[str, BranchInfo] = {}

    def add_branch(self, name: str, parent: str) -> None: ...
    def remove_branch(self, name: str) -> None:  # Auto-reparents children
    def get_stack(self, branch: str) -> list[str]: ...
    def get_descendants(self, branch: str) -> list[str]: ...
    def topological_sort(self, branches: list[str]) -> list[str]: ...
    def detect_trunk(self) -> str:  # Auto-detect main/master

class SyncState(BaseModel):
    active_command: Literal["sync", "submit"]
    todo_queue: list[str]
    current_index: int = 0
    original_head: str
```

### 2.3 Deliverables
- [ ] Write test_models.py (tests fail initially)
- [ ] Implement models.py until tests pass
- [ ] Verify isolated stack logic works

---

## Phase 3: Git Operations (`git_ops.py`)

### 3.1 Tests First (`test_git_ops.py`)
```python
# Unit tests (mocked subprocess)
def test_run_git_captures_stdout_stderr(mock_subprocess):
    """Output and errors are captured correctly."""

def test_run_git_raises_on_failure(mock_subprocess):
    """GitError raised with raw output on non-zero exit."""

def test_get_current_branch_parses_output(mock_subprocess):
    """Extracts branch name from git rev-parse."""

def test_is_workdir_clean_true_when_empty(mock_subprocess):
    """Returns True when git status --porcelain is empty."""

def test_is_workdir_clean_false_when_dirty(mock_subprocess):
    """Returns False when uncommitted changes exist."""

def test_detect_trunk_prefers_main(mock_subprocess):
    """Returns 'main' when both main and master exist."""

def test_detect_trunk_falls_back_to_master(mock_subprocess):
    """Returns 'master' when main doesn't exist."""

# Integration tests (real temp git repo)
def test_checkout_creates_branch(temp_git_repo):
    """checkout_branch(name, create=True) creates new branch."""

def test_is_rebase_in_progress_detects_state(temp_git_repo):
    """Detects .git/rebase-merge or .git/rebase-apply."""

def test_push_with_force_lease_sets_upstream(temp_git_repo):
    """First push uses -u flag for auto-tracking."""
```

### 3.2 Implementation
| Function | Purpose |
|----------|---------|
| `run_git(*args)` | Base wrapper, returns (stdout, stderr, returncode) |
| `get_current_branch()` | Returns current HEAD branch name |
| `is_workdir_clean()` | Checks for uncommitted changes |
| `detect_trunk()` | Auto-detect main vs master |
| `checkout_branch(name, create=False)` | Switch or create branch |
| `rebase(target, onto=None)` | Execute rebase, handle `--onto` |
| `is_rebase_in_progress()` | Check `.git/rebase-merge` or `.git/rebase-apply` |
| `rebase_continue()` | Run `git rebase --continue` |
| `rebase_abort()` | Run `git rebase --abort` |
| `fetch(remote, branch)` | Fetch specific branch |
| `is_ancestor(commit_a, commit_b)` | Check merge-base ancestry |
| `push(remote, branch, force_lease=True, set_upstream=False)` | Push with --force-with-lease, optional -u |

### 3.3 Deliverables
- [ ] Write test_git_ops.py (unit + integration tests)
- [ ] Implement git_ops.py until tests pass
- [ ] Verify detect_trunk() logic works

---

## Phase 4: Stack Manager (`stack_manager.py`)

### 4.1 Tests First (`test_stack_manager.py`)
```python
# Config file tests
def test_load_config_returns_default_when_missing(temp_git_repo):
    """Returns empty StackConfig if file doesn't exist."""

def test_save_and_load_config_roundtrip(temp_git_repo):
    """Config survives write/read cycle."""

def test_init_config_auto_detects_trunk(temp_git_repo):
    """Uses git_ops.detect_trunk() for initial trunk value."""

def test_config_file_in_gitignore_warning(temp_git_repo):
    """Warns if .gstack_config.json not in .gitignore."""

# State file tests
def test_state_file_lives_in_git_dir(temp_git_repo):
    """State saved to .git/.gstack_state.json."""

def test_has_pending_state_true_when_file_exists(temp_git_repo):
    """Detects interrupted operation."""

def test_clear_state_removes_file(temp_git_repo):
    """State file deleted after successful operation."""

# Integration with models
def test_add_branch_updates_parent_children(temp_git_repo):
    """Parent's children list includes new branch."""

def test_remove_branch_reparents_children(temp_git_repo):
    """Children point to grandparent after deletion."""
```

### 4.2 Implementation
| Function | Purpose |
|----------|---------|
| `load_config(repo_root)` | Read `.gstack_config.json`, return StackConfig |
| `save_config(config, repo_root)` | Write config to disk |
| `init_config(repo_root)` | Create initial config with auto-detected trunk |
| `load_state(repo_root)` | Read `.git/.gstack_state.json` |
| `save_state(state, repo_root)` | Write state file |
| `clear_state(repo_root)` | Delete state file |
| `has_pending_state(repo_root)` | Check if interrupted operation exists |

### 4.3 Deliverables
- [ ] Write test_stack_manager.py
- [ ] Implement stack_manager.py until tests pass
- [ ] Verify state file location is correct (.git/ not repo root)

---

## Phase 5: GitHub Operations (`gh_ops.py`)

### 5.1 Tests First (`test_gh_ops.py`)
```python
def test_run_gh_captures_output(mock_subprocess):
    """Output captured correctly from gh CLI."""

def test_is_gh_authenticated_returns_false_on_error(mock_subprocess):
    """Returns False when gh auth status fails."""

def test_get_pr_info_returns_none_when_no_pr(mock_subprocess):
    """Returns None instead of raising when PR doesn't exist."""

def test_get_pr_info_parses_json(mock_subprocess):
    """Extracts url, baseRefName, state from JSON output."""

def test_create_pr_uses_correct_base(mock_subprocess):
    """PR created with --base pointing to parent branch."""

def test_update_pr_base_calls_gh_pr_edit(mock_subprocess):
    """Uses 'gh pr edit --base' to update target."""

def test_is_pr_merged_checks_state(mock_subprocess):
    """Returns True when state is MERGED."""
```

### 5.2 Implementation
| Function | Purpose |
|----------|---------|
| `run_gh(*args)` | Base wrapper for `gh` CLI |
| `is_gh_authenticated()` | Check auth status |
| `get_pr_info(branch)` | Return PR URL, base branch, state (or None) |
| `create_pr(head, base, title=None, body=None)` | Create new PR |
| `update_pr_base(branch, new_base)` | Change PR target branch |
| `is_pr_merged(branch)` | Check if PR was merged |

### 5.3 Deliverables
- [ ] Write test_gh_ops.py
- [ ] Implement gh_ops.py until tests pass
- [ ] Handle "no PR exists" gracefully (return None, don't crash)

---

## Phase 6: Workflow Engine (`workflow_engine.py`)

### 6.1 Tests First (`test_workflow_engine.py`)
```python
# Sync workflow tests
def test_sync_fails_if_workdir_dirty(temp_git_repo):
    """Raises DirtyWorkdirError if uncommitted changes."""

def test_sync_fails_if_pending_state(temp_git_repo):
    """Raises PendingOperationError if state file exists."""

def test_sync_creates_state_file(temp_git_repo):
    """State file created before rebase starts."""

def test_sync_queue_in_topological_order(temp_git_repo):
    """Parent branches rebased before children."""

def test_sync_reparents_when_parent_merged(temp_git_repo, mock_gh):
    """Branch reparented to trunk when parent PR merged."""

def test_sync_stops_on_conflict(temp_git_repo):
    """State preserved, clear message printed on conflict."""

def test_sync_clears_state_on_success(temp_git_repo):
    """State file deleted after successful sync."""

def test_sync_returns_to_original_branch(temp_git_repo):
    """User ends up on same branch they started on."""

# Continue workflow tests
def test_continue_fails_without_state(temp_git_repo):
    """Error if no pending operation exists."""

def test_continue_resumes_from_current_index(temp_git_repo):
    """Picks up where sync left off."""

# Submit workflow tests
def test_submit_pushes_all_branches_in_stack(temp_git_repo, mock_gh):
    """All branches pushed with force-with-lease."""

def test_submit_creates_pr_if_missing(temp_git_repo, mock_gh):
    """New PR created with correct base."""

def test_submit_updates_pr_base_if_wrong(temp_git_repo, mock_gh):
    """PR base updated to match parent branch."""

def test_submit_sets_upstream_on_first_push(temp_git_repo, mock_gh):
    """First push uses -u flag."""

def test_submit_stores_pr_url_in_config(temp_git_repo, mock_gh):
    """pr_url field populated after PR creation."""
```

### 6.2 Sync Implementation
```
1. Validate: workdir clean, no pending state
2. Build queue: topological_sort(get_descendants(current_branch))
3. Save state: {command: "sync", queue, index: 0, original_head}
4. For each branch in queue:
   a. Checkout branch
   b. Check if parent merged → reparent to trunk
   c. Execute rebase (onto trunk or parent)
   d. On conflict: print instructions, EXIT (preserve state)
   e. On success: increment index, save state
5. Cleanup: delete state, checkout original_head
```

### 6.3 Continue Implementation
```
1. Load state (error if missing)
2. Verify rebase in progress
3. Run git rebase --continue
4. On conflict: EXIT
5. On success: resume sync loop from current_index + 1
```

### 6.4 Submit Implementation
```
1. Validate: workdir clean
2. For each branch in stack (bottom-up):
   a. Push with force-with-lease (+ -u if first push)
   b. Check PR exists
   c. Create or update PR base as needed
   d. Store pr_url in config
3. Save config
```

### 6.5 Deliverables
- [ ] Write test_workflow_engine.py
- [ ] Implement SyncWorkflow class
- [ ] Implement ContinueWorkflow class
- [ ] Implement SubmitWorkflow class
- [ ] Verify auto-reparent on merged parent
- [ ] Verify auto-upstream on first push

---

## Phase 7: CLI Interface (`main.py`)

### 7.1 Tests First (`test_cli.py`)
```python
from typer.testing import CliRunner

runner = CliRunner()

def test_init_creates_config_file(temp_git_repo):
    """gstack init creates .gstack_config.json."""
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (temp_git_repo / ".gstack_config.json").exists()

def test_init_auto_detects_trunk(temp_git_repo):
    """Trunk auto-detected from repo."""

def test_create_requires_clean_workdir(temp_git_repo):
    """Error if uncommitted changes exist."""

def test_create_adds_branch_to_config(temp_git_repo):
    """New branch registered with correct parent."""

def test_sync_shows_progress(temp_git_repo):
    """Output shows which branches are being rebased."""

def test_sync_conflict_shows_instructions(temp_git_repo):
    """Clear message on how to resolve and continue."""

def test_continue_without_conflict_errors(temp_git_repo):
    """Error if no rebase in progress."""

def test_abort_cleans_up_state(temp_git_repo):
    """State file removed, rebase aborted."""

def test_log_shows_stack_visualization(temp_git_repo):
    """ASCII tree of branch relationships."""

def test_delete_reparents_children(temp_git_repo):
    """Children moved to grandparent."""

def test_submit_shows_pr_urls(temp_git_repo, mock_gh):
    """PR URLs printed after creation."""

def test_verbose_shows_git_commands(temp_git_repo):
    """--verbose flag shows underlying git commands."""

def test_dry_run_no_side_effects(temp_git_repo):
    """--dry-run shows what would happen without doing it."""
```

### 7.2 Commands
```
gstack init [--trunk main]     # Initialize config in repo
gstack create <name>           # Create stacked branch
gstack sync                    # Rebase current stack
gstack continue                # Resume after conflict
gstack abort                   # Abort current operation
gstack submit                  # Push and manage PRs
gstack log                     # Show branch stack visualization
gstack delete <name>           # Remove branch from stack
```

### 7.3 Output Formatting
- Use `typer.echo()` with colors for status
- Show progress during multi-branch operations
- Display clear conflict resolution instructions

### 7.4 Deliverables
- [ ] Write test_cli.py
- [ ] Wire up all CLI commands
- [ ] Add `--verbose` flag for debug output
- [ ] Add `--dry-run` for sync/submit preview

---

## Phase 8: Edge Cases & Integration Tests

### 8.1 Additional Test Scenarios
```python
# Edge case tests (add to relevant test files)

def test_sync_handles_empty_stack(temp_git_repo):
    """No-op when branch has no children."""

def test_sync_diamond_dependency(temp_git_repo):
    """Handles A→B→D and A→C→D correctly."""

def test_create_from_non_tracked_branch(temp_git_repo):
    """Can create stack starting from any branch."""

def test_delete_last_branch_in_stack(temp_git_repo):
    """Stack removed from config when empty."""

def test_submit_without_gh_auth(temp_git_repo):
    """Clear error message if gh not authenticated."""

def test_sync_after_manual_rebase(temp_git_repo):
    """Handles case where user rebased manually."""

def test_config_corruption_recovery(temp_git_repo):
    """Graceful handling of malformed JSON."""
```

### 8.2 Deliverables
- [ ] Add edge case tests to each test file
- [ ] Verify test coverage > 80%
- [ ] Review and improve error messages

---

## Implementation Order (TDD)

| Phase | Tests | Implementation | Milestone |
|-------|-------|----------------|-----------|
| 1 | conftest.py fixtures | pyproject.toml, exceptions.py | pytest runs |
| 2 | test_models.py | models.py | Data structures work |
| 3 | test_git_ops.py | git_ops.py | Git wrapper works |
| 4 | test_stack_manager.py | stack_manager.py | Config persistence works |
| 5 | test_cli.py (init, create) | main.py (partial) | `gstack init/create` work |
| 6 | test_workflow_engine.py (sync) | workflow_engine.py (sync) | Sync works |
| 7 | test_cli.py (sync, continue, abort) | main.py (sync commands) | `gstack sync` works |
| 8 | test_gh_ops.py | gh_ops.py | GitHub integration works |
| 9 | test_workflow_engine.py (submit) | workflow_engine.py (submit) | Submit works |
| 10 | test_cli.py (submit, log, delete) | main.py (complete) | Full CLI works |

**TDD Cycle for each phase:**
1. Write failing tests
2. Implement minimum code to pass
3. Refactor
4. Move to next phase
