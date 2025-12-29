# gstack

A CLI tool for managing stacked Git branches with automated rebasing and GitHub PR management. Inspired by [Graphite](https://graphite.dev/).

## What is Branch Stacking?

Branch stacking is a workflow where you create a series of dependent branches, each building on the previous one. This allows you to:

- Break large features into smaller, reviewable PRs
- Get early feedback on foundational changes while continuing to build on top
- Keep your PRs focused and easy to review

```
main
 └── feature-auth          PR #1: Add authentication
      └── feature-auth-ui   PR #2: Add login UI (depends on #1)
           └── feature-tests PR #3: Add tests (depends on #2)
```

## Installation

### Quick Install (Recommended)

**macOS/Linux (curl):**
```bash
curl -fsSL https://raw.githubusercontent.com/nicomalacho/stack-branch/main/scripts/install.sh | bash
```

**macOS (Homebrew):**
```bash
brew tap nicomalacho/tap
brew install gs
```

**Direct Download:**
Download the latest release for your platform from [GitHub Releases](https://github.com/nicomalacho/stack-branch/releases/latest):
- `gs-macos-arm64` - macOS Apple Silicon
- `gs-macos-x86_64` - macOS Intel
- `gs-linux-x86_64` - Linux
- `gs-windows-x86_64.exe` - Windows

```bash
# Example: macOS Apple Silicon
curl -L https://github.com/nicomalacho/stack-branch/releases/latest/download/gs-macos-arm64 -o /usr/local/bin/gs
chmod +x /usr/local/bin/gs
```

### From Source (Development)

```bash
git clone https://github.com/nicomalacho/stack-branch.git
cd stack-branch
pip install -e ".[dev]"
```

After installation, use the `gs` command:

```bash
gs --help
```

**Git pass-through:** Any command not recognized by gstack is automatically passed to git, so you can use `gs` as a drop-in replacement for `git`:

```bash
gs status      # Same as: git status
gs add .       # Same as: git add .
gs commit -m "message"  # Same as: git commit -m "message"
gs diff        # Same as: git diff
gs log --oneline  # Same as: git log --oneline
```

## Quick Start

```bash
# Initialize gstack in your repository
cd your-repo
gs init

# Create your first stacked branch (works with uncommitted changes!)
gs create feature-auth

# Make changes and commit using gs (passes through to git)
gs add .
gs commit -m "Add authentication module"

# Push just this branch and create a PR
gs push

# Create another branch stacked on top
gs create feature-auth-ui

# Make more changes and commit
gs add .
gs commit -m "Add login UI"

# Push just this branch
gs push

# Or push all branches in the stack at once
gs submit
```

## Complete Example Workflow

Here's a real-world example of using gstack to implement a feature in multiple PRs:

### 1. Initialize gstack

```bash
cd my-project
gs init
# Output: Initialized gstack with trunk branch 'main'.
```

### 2. Create the first branch in your stack

```bash
gs create add-user-model
# Output: Created branch 'add-user-model' on top of 'main'.
```

Make your changes:

```bash
# Create user model
echo "class User: pass" > user.py
git add user.py
git commit -m "Add User model"
```

### 3. Push and create PR for current branch

```bash
gs push
# Output: Pushed and created PR: https://github.com/org/repo/pull/1
```

### 4. Stack another branch on top

```bash
gs create add-user-api
# Output: Created branch 'add-user-api' on top of 'add-user-model'.
```

Make more changes:

```bash
# Add API endpoint
echo "def get_user(): pass" > api.py
git add api.py
git commit -m "Add user API endpoint"
```

### 5. Push this branch too

```bash
gs push
# Output: Pushed and created PR: https://github.com/org/repo/pull/2
```

The PR is automatically created with `add-user-model` as the base branch.

### 6. View your stack

```bash
gs log
# Output:
# Trunk: main
#   * add-user-model (https://github.com/org/repo/pull/1)
#       add-user-api (https://github.com/org/repo/pull/2)
```

The `*` indicates your current branch.

### 7. Update the first branch

If you need to make changes to `add-user-model`:

```bash
git checkout add-user-model
# Make changes
git add .
git commit -m "Update User model"
gs push  # Push just this branch
```

### 8. Sync the stack

After pushing changes to `add-user-model`, sync the dependent branches:

```bash
git checkout add-user-api
gs sync
# Output:
# Synced 2 branch(es):
#   - add-user-model
#   - add-user-api

gs push  # Push the rebased branch
```

### 9. Handle merge conflicts

If conflicts occur during sync:

```bash
gs sync
# Output:
# Conflict in branch 'add-user-model'.
# Resolve the conflicts, stage the files, then run 'gs continue'.
# Or run 'gs abort' to cancel the sync.
```

Resolve conflicts:

```bash
# Fix conflicts in your editor
git add <resolved-files>
gs continue
```

Or abort:

```bash
gs abort
# Output: Sync aborted.
```

### 10. After PR is merged

When you run `gs sync`, gstack automatically detects merged branches and offers to clean them up:

```bash
gs sync
# Output:
# The following branches have been merged:
#   - add-user-model
#
# Delete merged branch 'add-user-model'? [Y/n]: y
#   Deleted 'add-user-model'
#
# Synced 1 branch(es):
#   - add-user-api
```

Child branches are automatically reparented to the deleted branch's parent.

## Features

### Stack Diagrams on PRs

When you run `gs submit` or `gs push`, gstack automatically adds a mermaid diagram comment to your PRs showing the stack structure:

```mermaid
graph TD
    main[main]
    add-user-model[add-user-model [#1]]
    main --> add-user-model
    add-user-api[add-user-api [#2]]
    add-user-model --> add-user-api
```

This helps reviewers understand how the PR fits into the larger feature.

### Automatic Merged Branch Detection

Running `gs sync` automatically checks for merged PRs and prompts you to delete the local branches, keeping your stack clean.

### Git Pass-Through

Any unrecognized command is passed directly to git, so you can use `gs` as your primary git interface:

```bash
gs status           # git status
gs add .            # git add .
gs commit -m "msg"  # git commit -m "msg"
gs diff             # git diff
gs stash            # git stash
gs rebase -i HEAD~3 # git rebase -i HEAD~3
```

This means you only need to type `gs` instead of `git` for all your version control needs.

### Create with Uncommitted Changes

Unlike some stacking tools, `gs create` works even when you have uncommitted changes in your working directory. This enables a natural workflow:

```bash
# Start working on a feature
echo "new code" > feature.py

# Decide to put it on a new branch
gs create my-feature

# Now commit it
gs add .
gs commit -m "Add new feature"
```

## Commands Reference

### `gs init`

Initialize gstack in the current repository.

```bash
gs init                    # Auto-detect trunk (main or master)
gs init --trunk develop    # Specify trunk branch
gs init --force            # Reinitialize (clears existing config)
```

### `gs create <name>`

Create a new stacked branch.

```bash
gs create feature          # Stack on current branch
gs create feature --parent main  # Stack on specific branch
```

### `gs push`

Push the current branch and create/update its PR.

```bash
gs push
```

- Pushes only the current branch (with force-with-lease)
- Creates PR if none exists
- Updates PR base if it doesn't match the parent
- Adds stack diagram comment to the PR

**Use case:** Quick iteration on a single branch without affecting the rest of the stack.

### `gs submit`

Push all branches in the stack and create/update their PRs.

```bash
gs submit
```

- Pushes all branches in the current stack
- Creates PRs for branches without one
- Updates PR base branches if they don't match the parent
- Adds stack diagram comments to all PRs

**Use case:** Push the entire stack after making changes across multiple branches.

### `gs sync`

Rebase the current stack onto the latest trunk.

```bash
gs sync
```

- Detects merged branches and offers to delete them
- Syncs all branches from the current branch's stack (ancestors and descendants)
- Preserves state on conflict for `gs continue`

### `gs continue`

Continue a sync operation after resolving conflicts.

```bash
# After resolving conflicts and staging files
gs continue
```

### `gs abort`

Abort the current sync operation.

```bash
gs abort
```

### `gs log`

Show the current stack structure.

```bash
gs log
```

### `gs delete <name>`

Delete a branch from the stack.

```bash
gs delete feature          # Delete branch
gs delete feature --force  # Force delete unmerged branch
```

Child branches are automatically reparented to the deleted branch's parent.

## Requirements

- Git
- Python 3.9+
- GitHub CLI (`gh`) for push/submit functionality

## Configuration

gstack stores its configuration in `.git/.gstack_config.json`. This file tracks:

- Trunk branch name
- Tracked branches and their parent relationships
- PR URLs

Since the config is stored inside the `.git/` directory, it is automatically ignored by git and does not need to be added to `.gitignore`. Note that this means the stack configuration is local to each clone of the repository.

## License

MIT
