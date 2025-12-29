"""Custom exceptions for gstack."""


class GstackError(Exception):
    """Base exception for all gstack errors."""

    pass


class GitError(GstackError):
    """Error executing a git command."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


class DirtyWorkdirError(GstackError):
    """Working directory has uncommitted changes."""

    def __init__(self) -> None:
        super().__init__(
            "Working directory is not clean. Please commit or stash your changes first."
        )


class RebaseConflictError(GstackError):
    """Rebase encountered merge conflicts."""

    def __init__(self, branch: str) -> None:
        self.branch = branch
        super().__init__(
            f"Conflict while rebasing '{branch}'. "
            "Fix the conflicts, stage the files, then run 'gstack continue'."
        )


class PendingOperationError(GstackError):
    """There is already a pending operation (sync/submit) in progress."""

    def __init__(self, operation: str) -> None:
        self.operation = operation
        super().__init__(
            f"A '{operation}' operation is already in progress. "
            "Run 'gstack continue' to resume or 'gstack abort' to cancel."
        )


class NoPendingOperationError(GstackError):
    """No pending operation to continue or abort."""

    def __init__(self) -> None:
        super().__init__("No pending operation to continue or abort.")


class NotAGitRepoError(GstackError):
    """Current directory is not a git repository."""

    def __init__(self) -> None:
        super().__init__("Not a git repository. Please run this command inside a git repo.")


class NotInitializedError(GstackError):
    """gstack has not been initialized in this repository."""

    def __init__(self) -> None:
        super().__init__("gstack is not initialized. Run 'gstack init' first.")


class BranchNotFoundError(GstackError):
    """Branch not found in the stack configuration."""

    def __init__(self, branch: str) -> None:
        self.branch = branch
        super().__init__(f"Branch '{branch}' is not tracked by gstack.")


class BranchAlreadyExistsError(GstackError):
    """Branch already exists in git or stack."""

    def __init__(self, branch: str) -> None:
        self.branch = branch
        super().__init__(f"Branch '{branch}' already exists.")


class GhError(GstackError):
    """Error executing a gh (GitHub CLI) command."""

    def __init__(self, message: str, returncode: int = 1, stderr: str = "") -> None:
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(message)


class GhNotAuthenticatedError(GstackError):
    """GitHub CLI is not authenticated."""

    def __init__(self) -> None:
        super().__init__("GitHub CLI is not authenticated. Run 'gh auth login' first.")
