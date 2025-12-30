# Development Guidelines for AI Agents

## Test-Driven Development (TDD)

All new functionality MUST follow TDD:

1. **Write tests FIRST** - Before writing any implementation code
2. **Run tests** - Confirm they fail (red)
3. **Implement feature** - Write the minimum code to pass
4. **Run tests** - Confirm they pass (green)
5. **Refactor** - Clean up while keeping tests green

## Testing Commands

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_file.py

# Run specific test class
uv run pytest tests/test_file.py::TestClassName

# Run with verbose output
uv run pytest -v
```

## Code Patterns

### Adding a New CLI Command

1. Add tests in `tests/test_cli.py`
2. Add command in `gstack/main.py` using `@app.command()` decorator
3. Add workflow logic in `gstack/workflow_engine.py` if complex
4. Update `GSTACK_COMMANDS` set in `main.py`

### Adding Git Operations

1. Add tests in `tests/test_git_ops.py`
2. Add function in `gstack/git_ops.py`
3. Use `run_git()` wrapper for all git commands

### Adding GitHub Operations

1. Add tests in `tests/test_gh_ops.py`
2. Add function in `gstack/gh_ops.py`
3. Use `run_gh()` wrapper for all gh commands

## File Structure

- `gstack/main.py` - CLI entry point and commands
- `gstack/workflow_engine.py` - Complex multi-step workflows
- `gstack/git_ops.py` - Git command wrappers
- `gstack/gh_ops.py` - GitHub CLI wrappers
- `gstack/stack_manager.py` - Config management
- `gstack/models.py` - Data models (StackConfig, BranchInfo)
- `gstack/exceptions.py` - Custom exceptions
