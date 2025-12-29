Here is a comprehensive System Design Specification. You can copy and paste this entire plan directly into Claude Code (or any AI coding assistant). It provides the exact data structures, algorithms, and edge-case handling logic required to build the tool robustly.

System Design Spec: gstack (Graphite Clone)
1. Project Overview
Goal: Create a Python CLI tool named gstack that manages stacked Git branches, automates recursive rebasing, and handles chained GitHub PRs. Dependencies: git (>=2.38), gh (GitHub CLI), Python 3.9+. Core Philosophy: Wrap native Git commands. Do not reimplement Git internal logic. Use a local JSON file to track the "meta-graph" of branch dependencies.

2. Data Structures
A. The Stack Manifest (.gstack_config.json)
Located in the repository root (should be added to .gitignore). Purpose: Tracks parent-child relationships that Git is unaware of.

JSON

{
  "trunk": "main",
  "branches": {
    "feature-login": {
      "parent": "main",
      "children": ["feature-login-ui"],
      "pr_url": "https://github.com/..."
    },
    "feature-login-ui": {
      "parent": "feature-login",
      "children": [],
      "pr_url": null
    }
  }
}
B. The State File (.gstack_state.json)
Located in .git/ folder. Purpose: Persists execution state to handle interruptions (like merge conflicts).

JSON

{
  "active_command": "sync",
  "todo_queue": ["feature-login", "feature-login-ui"],
  "current_index": 0,
  "original_head": "feature-login-ui"
}
3. Module Architecture
The codebase should be split into these modules:

main.py: Entry point. Uses typer or argparse to handle CLI commands.

git_ops.py: Wrapper for subprocess.run(["git", ...]). Handles all raw git interactions.

stack_manager.py: Reads/writes .gstack_config.json. Handles graph logic (finding children, reparenting).

gh_ops.py: Wrapper for subprocess.run(["gh", ...]). Handles PR creation and status checks.

workflow_engine.py: The "brain". Executes the complex multi-step logic (Sync, Submit) and manages the State File.

4. detailed Command Logic
Command: gstack create <branch_name>
Check Status: Ensure working directory is clean.

Identify Parent: Store the current branch name as parent.

Git Operation: git checkout -b <branch_name>.

Update Config:

Add <branch_name> to config with parent.

Append <branch_name> to parent's children list.

Save .gstack_config.json.

Command: gstack sync (The Complex One)
Algorithm:

Init State: Write .gstack_state.json with the full list of branches to rebase (topological sort from root to leaf).

Execution Loop (managed by workflow_engine):

Step A (Fetch): git fetch origin <trunk>.

Step B (Check Parent): For the current branch in queue:

Check if its parent has been merged into trunk (using git merge-base --is-ancestor or gh pr view).

If Merged: Update config to set parent = trunk. Use git rebase --onto origin/trunk <old_parent> <current_branch>.

If Not Merged: Use git rebase <parent>.

Step C (Conflict Handling):

If git rebase fails (exit code != 0):

Print: "Conflict detected. Fix files, git add, then run gstack continue."

EXIT PROCESS (Do not cleanup state file).

Cleanup: If loop finishes successfully, delete .gstack_state.json.

Command: gstack continue
Load State: Read .gstack_state.json. If missing, error out.

Verify Git: Check if git status shows a rebase in progress.

Resume Git: Run git rebase --continue.

If this fails again (another conflict), Exit.

If this succeeds, increment current_index in the State File and call the Execution Loop from sync.

Command: gstack submit
Traverse: specific stack or all stacks.

Push: git push origin <branch> --force-with-lease.

PR Check: gh pr view <branch> --json url,baseRefName.

PR Create/Update:

If PR doesn't exist: gh pr create --head <branch> --base <parent>.

If PR exists but base is wrong (e.g., points to main instead of parent): gh pr edit <branch> --base <parent>.

5. Specific Implementation Constraints for Claude
Libraries: Use typer for CLI, pydantic for data validation (optional but good), subprocess for shell commands.

Safety: Always check for a dirty working directory (uncommitted changes) before running sync or create. Fail if dirty.

Git Output: Capture stdout and stderr. If a git command fails, show the user the raw git error.

Recursion: When calculating the stack for sync, use a recursive function to find all descendants of the current branch.