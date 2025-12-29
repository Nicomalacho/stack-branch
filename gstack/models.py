"""Data models for gstack configuration and state."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BranchInfo(BaseModel):
    """Information about a tracked branch in the stack.

    Attributes:
        parent: The parent branch name (trunk or another stacked branch).
        children: List of child branch names that depend on this branch.
        pr_url: GitHub PR URL if one exists for this branch.
    """

    parent: str
    children: list[str] = Field(default_factory=list)
    pr_url: str | None = None


class StackConfig(BaseModel):
    """Configuration for gstack, tracking branch relationships.

    This is persisted to .gstack_config.json in the repository root.

    Attributes:
        trunk: The main/master branch name (auto-detected or specified).
        branches: Map of branch name to BranchInfo for all tracked branches.
    """

    trunk: str = "main"
    branches: dict[str, BranchInfo] = Field(default_factory=dict)

    def add_branch(self, name: str, parent: str) -> None:
        """Add a new branch to the stack.

        Args:
            name: The new branch name.
            parent: The parent branch (trunk or existing stacked branch).

        The branch is added to the branches dict, and if the parent is not
        the trunk, the parent's children list is updated.
        """
        self.branches[name] = BranchInfo(parent=parent)

        # Update parent's children list (if parent is tracked, not trunk)
        if parent in self.branches:
            self.branches[parent].children.append(name)

    def remove_branch(self, name: str) -> None:
        """Remove a branch from the stack, reparenting its children.

        Args:
            name: The branch to remove.

        Raises:
            KeyError: If the branch is not tracked.

        Children of the removed branch are reparented to the grandparent.
        """
        if name not in self.branches:
            raise KeyError(f"Branch '{name}' not found")

        branch_info = self.branches[name]
        grandparent = branch_info.parent

        # Reparent children to grandparent
        for child in branch_info.children:
            self.branches[child].parent = grandparent
            # Add to grandparent's children if grandparent is tracked
            if grandparent in self.branches:
                self.branches[grandparent].children.append(child)

        # Remove from parent's children list
        if branch_info.parent in self.branches:
            self.branches[branch_info.parent].children.remove(name)

        # Remove the branch
        del self.branches[name]

    def get_stack(self, branch: str) -> list[str]:
        """Get the full stack from trunk to the given branch.

        Args:
            branch: The branch to get the stack for.

        Returns:
            List of branch names from trunk to the given branch (inclusive).

        Raises:
            KeyError: If the branch is not tracked and is not the trunk.
        """
        if branch == self.trunk:
            return [self.trunk]

        if branch not in self.branches:
            raise KeyError(f"Branch '{branch}' not found")

        # Build path from branch to trunk
        path = [branch]
        current = branch

        while current != self.trunk:
            parent = self.branches[current].parent
            path.append(parent)
            if parent == self.trunk:
                break
            current = parent

        # Reverse to get trunk -> branch order
        return list(reversed(path))

    def get_descendants(self, branch: str) -> list[str]:
        """Get all descendants of a branch recursively.

        Args:
            branch: The branch to get descendants for.

        Returns:
            List of all descendant branch names (children, grandchildren, etc.).
        """
        descendants: list[str] = []

        # Get direct children
        if branch == self.trunk:
            # For trunk, find all branches with trunk as parent
            children = [name for name, info in self.branches.items() if info.parent == self.trunk]
        elif branch in self.branches:
            children = self.branches[branch].children
        else:
            return []

        # Recursively get descendants
        for child in children:
            descendants.append(child)
            descendants.extend(self.get_descendants(child))

        return descendants

    def topological_sort(self, branches: list[str]) -> list[str]:
        """Sort branches so that parents come before children.

        Args:
            branches: List of branch names to sort.

        Returns:
            Sorted list where each branch appears after its parent.
        """
        if not branches:
            return []

        # Build a set for O(1) lookup
        branch_set = set(branches)

        # Calculate depth (distance from trunk) for each branch
        def get_depth(branch: str) -> int:
            if branch == self.trunk or branch not in self.branches:
                return 0
            return len(self.get_stack(branch)) - 1

        # Sort by depth (parents have lower depth than children)
        # Use stable sort to preserve relative order of siblings
        return sorted(branches, key=get_depth)


class SyncState(BaseModel):
    """State for an in-progress sync or submit operation.

    This is persisted to .git/.gstack_state.json to survive interruptions.

    Attributes:
        active_command: The command being executed ("sync" or "submit").
        todo_queue: Ordered list of branches to process.
        current_index: Index of the current branch being processed.
        original_head: The branch the user was on when starting the operation.
    """

    active_command: Literal["sync", "submit"]
    todo_queue: list[str]
    current_index: int = 0
    original_head: str

    @property
    def current_branch(self) -> str | None:
        """Get the current branch being processed, or None if done."""
        if self.current_index >= len(self.todo_queue):
            return None
        return self.todo_queue[self.current_index]

    @property
    def is_complete(self) -> bool:
        """Check if all branches have been processed."""
        return self.current_index >= len(self.todo_queue)
