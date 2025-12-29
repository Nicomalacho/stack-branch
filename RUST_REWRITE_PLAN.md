# Plan: Rewrite gstack CLI in Rust

## Goal
Rewrite the gstack CLI tool from Python to Rust for instant startup time (~0.01s vs ~12s cold / ~0.25s cached).

## Current State
- **Python codebase:** 2,139 lines across 7 modules
- **Test suite:** 183 tests across 9 files
- **Dependencies:** typer, pydantic, rich + external git/gh CLI

## Rust Equivalents

| Python | Rust | Purpose |
|--------|------|---------|
| typer | clap | CLI framework |
| pydantic | serde + serde_json | Data serialization |
| rich | colored | Terminal colors |
| subprocess | std::process::Command | External commands |

---

## Implementation Plan

### Phase 1: Project Setup

**1.1 Initialize Rust project**
- Create `gstack-rs/` directory with Cargo workspace
- Configure `Cargo.toml` with dependencies:
  ```toml
  [dependencies]
  clap = { version = "4", features = ["derive"] }
  serde = { version = "1", features = ["derive"] }
  serde_json = "1"
  thiserror = "1"
  colored = "2"
  ```

**1.2 Set up CI/CD**
- Update `.github/workflows/release.yml` for Rust cross-compilation
- Use `cross` or `cargo-zigbuild` for multi-platform builds

---

### Phase 2: Core Data Structures

**2.1 Models (`src/models.rs`)**
Port from `gstack/models.py` (193 lines):

```rust
#[derive(Serialize, Deserialize, Clone)]
pub struct BranchInfo {
    pub parent: String,
    #[serde(default)]
    pub children: Vec<String>,
    pub pr_url: Option<String>,
}

#[derive(Serialize, Deserialize, Default)]
pub struct StackConfig {
    pub trunk: String,
    pub branches: HashMap<String, BranchInfo>,
}

#[derive(Serialize, Deserialize)]
pub struct SyncState {
    pub active_command: String,
    pub todo_queue: Vec<String>,
    pub current_index: usize,
    pub original_head: String,
}
```

**2.2 Implement StackConfig methods**
- `add_branch(name, parent)`
- `remove_branch(name)` with auto-reparenting
- `get_stack(branch) -> Vec<String>`
- `get_descendants(branch) -> Vec<String>`
- `topological_sort(branches) -> Vec<String>`

---

### Phase 3: Error Handling

**3.1 Errors (`src/errors.rs`)**
Port from `gstack/exceptions.py` (100 lines):

```rust
#[derive(thiserror::Error, Debug)]
pub enum GstackError {
    #[error("Git error: {message}")]
    Git { message: String, returncode: i32 },
    #[error("Working directory has uncommitted changes")]
    DirtyWorkdir,
    #[error("Rebase conflict in branch '{0}'")]
    RebaseConflict(String),
    #[error("Operation '{0}' is already in progress")]
    PendingOperation(String),
    #[error("No pending operation to continue/abort")]
    NoPendingOperation,
    #[error("Not a git repository")]
    NotAGitRepo,
    #[error("gstack not initialized")]
    NotInitialized,
    #[error("Branch '{0}' not found")]
    BranchNotFound(String),
    #[error("Branch '{0}' already exists")]
    BranchAlreadyExists(String),
    #[error("GitHub CLI error: {message}")]
    Gh { message: String, returncode: i32 },
    #[error("GitHub CLI not authenticated")]
    GhNotAuthenticated,
}
```

---

### Phase 4: Git Operations

**4.1 Git wrapper (`src/git_ops.rs`)**
Port from `gstack/git_ops.py` (304 lines):

| Function | Command |
|----------|---------|
| `run_git(args)` | `Command::new("git").args(args)` |
| `get_current_branch()` | `git rev-parse --abbrev-ref HEAD` |
| `is_workdir_clean()` | `git status --porcelain` |
| `detect_trunk()` | Try main, fallback to master |
| `checkout_branch(name, create)` | `git checkout [-b]` |
| `branch_exists(name)` | `git rev-parse --verify` |
| `is_ancestor(a, b)` | `git merge-base --is-ancestor` |
| `rebase(target, onto, upstream)` | `git rebase [--onto]` |
| `is_rebase_in_progress()` | Check `.git/rebase-merge` |
| `rebase_continue/abort()` | `git rebase --continue/--abort` |
| `push(branch, force, set_upstream)` | `git push [--force-with-lease] [-u]` |
| `get_repo_root()` | `git rev-parse --show-toplevel` |
| `delete_branch(name, force)` | `git branch -d/-D` |

---

### Phase 5: GitHub Operations

**5.1 GitHub CLI wrapper (`src/gh_ops.rs`)**
Port from `gstack/gh_ops.py` (313 lines):

| Function | Command |
|----------|---------|
| `run_gh(args)` | `Command::new("gh").args(args)` |
| `is_gh_authenticated()` | `gh auth status` |
| `get_pr_info(branch)` | `gh pr view --json` |
| `create_pr(head, base, title, body)` | `gh pr create` |
| `update_pr_base(branch, new_base)` | `gh pr edit --base` |
| `is_pr_merged(branch)` | Check state == "MERGED" |
| `add_or_update_stack_comment()` | `gh pr comment` |
| `generate_stack_mermaid()` | Build mermaid string |

---

### Phase 6: Config/State Management

**6.1 Stack manager (`src/stack_manager.rs`)**
Port from `gstack/stack_manager.py` (233 lines):

| Function | Purpose |
|----------|---------|
| `load_config(repo_root)` | Read `.git/.gstack_config.json` |
| `save_config(config, repo_root)` | Write JSON |
| `init_config(repo_root, trunk, force)` | Create config |
| `is_initialized(repo_root)` | Check file exists |
| `load_state/save_state/clear_state` | State file ops |
| `register_branch/unregister_branch` | Config mutations |

---

### Phase 7: Workflow Engine

**7.1 Workflow engine (`src/workflow_engine.rs`)**
Port from `gstack/workflow_engine.py` (571 lines):

**run_sync:**
1. Validate workdir clean, no pending state
2. Build queue (topological sort)
3. Save state → loop (checkout → rebase) → cleanup

**run_submit:**
1. Validate workdir clean, gh authenticated
2. For each branch: push → get/create PR → update base
3. Post mermaid diagrams

**run_push:** Single-branch version of submit

**run_continue/abort:** Resume or cancel operation

---

### Phase 8: CLI Layer

**8.1 Main CLI (`src/main.rs`)**
Port from `gstack/main.py` (422 lines):

```rust
#[derive(Parser)]
#[command(name = "gs")]
struct Cli {
    #[command(subcommand)]
    command: Option<Commands>,
    #[arg(trailing_var_arg = true)]
    git_args: Vec<String>,
}

#[derive(Subcommand)]
enum Commands {
    Init { trunk: Option<String>, force: bool },
    Create { name: String, parent: Option<String> },
    Sync, Continue, Abort, Push, Submit, Log,
    Delete { name: String, force: bool },
}
```

**Git pass-through:** Forward unrecognized commands to `git`.

---

### Phase 9: Testing

- Use `tempfile` for temporary git repos
- Use `assert_cmd` for CLI tests
- Port all 183 tests

---

### Phase 10: Release

**10.1 Update workflow**
```yaml
- name: Build
  run: |
    cargo build --release
    mv target/release/gs dist/${{ matrix.artifact_name }}
```

**10.2 Update Homebrew formula** with new SHA256s

---

## File Structure

```
gstack-rs/
├── Cargo.toml
├── src/
│   ├── main.rs
│   ├── lib.rs
│   ├── models.rs
│   ├── errors.rs
│   ├── git_ops.rs
│   ├── gh_ops.rs
│   ├── stack_manager.rs
│   └── workflow_engine.rs
└── tests/
    └── *.rs
```

---

## Expected Performance

| Metric | Python (Nuitka) | Rust |
|--------|-----------------|------|
| Cold start | ~12s | ~0.01s |
| Warm start | ~0.25s | ~0.01s |
| Binary size | ~13MB | ~3-5MB |

---

## Recommended Order

1. **Phase 1-3:** Setup + models + errors
2. **Phase 4-5:** Git/gh wrappers
3. **Phase 6:** Config management
4. **Phase 7:** Workflow engine
5. **Phase 8:** CLI layer
6. **Phase 9-10:** Testing + release
