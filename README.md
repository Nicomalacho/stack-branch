# gstack

A CLI tool for managing stacked Git branches with automated rebasing and GitHub PR management.

## Installation

```bash
uv pip install -e ".[dev]"
```

## Usage

```bash
gstack init           # Initialize in current repo
gstack create feature # Create a stacked branch
gstack sync           # Rebase current stack
gstack submit         # Push and create PRs
```
