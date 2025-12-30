# gstack Improvements Plan

## Issues to Fix

| # | Issue | File | Severity |
|---|-------|------|----------|
| 1 | `gs add -u -p` fails (interactive mode) | `main.py` | High |
| 2 | `gs push` not creating PRs | `workflow_engine.py` | High |
| 3 | `gs submit` not creating PRs | `workflow_engine.py` | High |
| 4 | No PR description added | `workflow_engine.py`, `gh_ops.py` | Medium |
| 5 | Mermaid diagram parse error | `gh_ops.py` | High |
| 6 | Dependent PRs not updated after parent changes | `workflow_engine.py` | Medium |
| 7 | Auto-submit after conflict resolution | `workflow_engine.py` | Feature |
| 8 | Auto-squash before rebase | `workflow_engine.py`, `git_ops.py` | Feature |

---

## Fix 1: Git Passthrough Interactive Mode

**Problem:** `gs add -u -p` fails because `subprocess.run()` doesn't preserve TTY for interactive commands like `-p` (patch mode).

**File:** `gstack/main.py` (lines 412-418)

**Current code:**
```python
git_args = ["git"] + sys.argv[1:]
result = subprocess.run(git_args)
sys.exit(result.returncode)
```

**Fix:** Use `os.execvp()` to replace the process entirely, preserving TTY:
```python
git_args = ["git"] + sys.argv[1:]
os.execvp("git", git_args)
```

This hands control directly to git, preserving all interactive features.

---

## Fix 2 & 3: PRs Not Being Created

**Problem:** PR creation failures are silently swallowed. Exceptions caught but not logged.

**File:** `gstack/workflow_engine.py`

**Locations:**
- `run_submit()` lines 360-368
- `run_push()` lines 510-522

**Current code:**
```python
try:
    result = gh_ops.create_pr(head=branch, base=parent)
    created_prs.append(branch)
except Exception:
    pass  # Silent failure!
```

**Fix:** Add logging and surface errors to user:
```python
try:
    result = gh_ops.create_pr(head=branch, base=parent)
    created_prs.append(branch)
    typer.echo(f"  Created PR: {result.url}")
except Exception as e:
    typer.echo(f"  Warning: Failed to create PR for {branch}: {e}", err=True)
```

Also add verbose output for all operations (push, PR create, base update).

---

## Fix 4: No PR Description

**Problem:** `create_pr()` accepts `body` parameter but it's never passed from workflow_engine.

**Files:**
- `gstack/workflow_engine.py` (lines 362, 513)
- `gstack/gh_ops.py` (line 131)

**Current call:**
```python
gh_ops.create_pr(head=branch, base=parent)
```

**Fix:** Generate a default PR body with stack info:
```python
body = f"Part of stack based on `{parent}`.\n\nCreated with gstack."
gh_ops.create_pr(head=branch, base=parent, body=body)
```

---

## Fix 5: Mermaid Diagram Parse Error

**Problem:** Raw HTML `<a>` tags in mermaid nodes cause parse errors on GitHub.

**File:** `gstack/gh_ops.py` (line 298)

**Current code:**
```python
lines.append(f"    {name}[<a href='{info.pr_url}'>{label}</a>]")
```

**Error:**
```
Parse error: Expecting 'SQE', got 'SQS'
```

**Fix:** Use mermaid's `click` directive instead of HTML:
```python
# Node without HTML
lines.append(f"    {name}[{label}]")
# Add click action for link
if info.pr_url:
    lines.append(f"    click {name} href \"{info.pr_url}\" _blank")
```

This produces valid mermaid that renders clickable nodes.

---

## Fix 6: Dependent PRs Not Updated

**Problem:** When parent branch changes, child PRs should be rebased and pushed.

**Analysis:** Current `submit` only updates the PR *base branch reference* on GitHub, but doesn't actually rebase the child branches onto the updated parent.

**File:** `gstack/workflow_engine.py`

**Current flow:**
1. Push all branches
2. Create/update PRs
3. Update PR base if mismatched

**Fixed flow:**
1. Sync (rebase) all branches first
2. Push all branches
3. Create/update PRs

**Fix:** Call `run_sync()` at the start of `run_submit()`:
```python
def run_submit(repo_root: Path) -> SubmitResult:
    # First sync all branches to ensure they're up to date
    sync_result = run_sync(repo_root)
    if not sync_result.success:
        return SubmitResult(success=False, message=sync_result.message)

    # Then push and create PRs...
```

---

## Fix 7: Auto-Submit After Conflict Resolution

**Problem:** After `gs continue` resolves conflicts, user must manually run `gs submit`.

**File:** `gstack/workflow_engine.py` (function `run_continue`)

**Fix:** Add auto-submit after successful continue:
```python
def run_continue(repo_root: Path) -> SyncResult:
    # ... existing continue logic ...

    if result.success:
        # Auto-submit after successful sync
        typer.echo("Sync complete. Pushing changes...")
        submit_result = run_submit(repo_root)
        result.message += f"\n{submit_result.message}"

    return result
```

---

## Fix 8: Auto-Squash Before Rebase

**Problem:** Multiple commits cause more merge conflicts. Squashing first reduces conflicts.

**Files:**
- `gstack/git_ops.py` - Add `squash_commits()` function
- `gstack/workflow_engine.py` - Call squash in `_execute_sync()`

**New function in git_ops.py:**
```python
def squash_commits(branch: str, parent: str) -> GitResult:
    """Squash all commits on branch since parent into one."""
    # Get commit count
    result = run_git("rev-list", "--count", f"{parent}..{branch}")
    count = int(result.stdout.strip())

    if count <= 1:
        return GitResult(stdout="", stderr="", returncode=0)  # Nothing to squash

    # Soft reset to parent, keeping changes staged
    run_git("reset", "--soft", parent)

    # Get original commit message from first commit
    msg_result = run_git("log", "--format=%B", "-1", f"{parent}..HEAD@{1}")
    message = msg_result.stdout.strip() or f"Squashed {count} commits"

    # Create single commit
    return run_git("commit", "-m", message)
```

**Update in workflow_engine.py `_execute_sync()`:**
```python
# Before rebase
git_ops.checkout_branch(branch)

# Squash commits first
squash_result = git_ops.squash_commits(branch, parent)
if squash_result.returncode != 0:
    typer.echo(f"  Warning: Could not squash {branch}")

# Then rebase
result = git_ops.rebase(parent, check=False)
```

---

## Implementation Order (TDD)

**⚠️ For each fix: Write tests FIRST, then implement the fix.**

1. **Fix 1** - Git passthrough (quick win, unblocks git commands)
   - [ ] Write test for `-m` flag passthrough
   - [ ] Write test for `-u -p` interactive passthrough
   - [ ] Implement fix

2. **Fix 5** - Mermaid diagram (quick win, visible improvement)
   - [ ] Write test for valid mermaid syntax
   - [ ] Write test for clickable links
   - [ ] Implement fix

3. **Fix 2 & 3** - PR creation logging (debugging visibility)
   - [ ] Write test for PR creation error logging
   - [ ] Implement fix

4. **Fix 4** - PR description (quick enhancement)
   - [ ] Write test for PR body content
   - [ ] Implement fix

5. **Fix 6** - Dependent PR updates (important workflow fix)
   - [ ] Write test for sync-before-submit
   - [ ] Implement fix

6. **Fix 8** - Auto-squash (reduces conflicts)
   - [ ] Write test for `squash_commits()` function
   - [ ] Write test for sync squashing commits
   - [ ] Implement fix

7. **Fix 7** - Auto-submit after continue (convenience feature)
   - [ ] Write test for auto-submit after continue
   - [ ] Implement fix

8. **Task 9** - Update README
   - [ ] Document new behaviors

---

## Files to Modify

| File | Changes |
|------|---------|
| `gstack/main.py` | Fix 1: Use `os.execvp()` for git passthrough |
| `gstack/git_ops.py` | Fix 8: Add `squash_commits()` function |
| `gstack/gh_ops.py` | Fix 5: Use mermaid `click` directive |
| `gstack/workflow_engine.py` | Fixes 2-4, 6-8: Logging, body, sync-before-submit, squash, auto-submit |

---

## Task 9: Update README

**File:** `README.md`

**Changes needed:**
- Document auto-squash behavior during sync
- Document auto-submit after continue
- Update workflow examples to reflect new behavior
- Add troubleshooting section for common issues
- Update installation instructions if needed
