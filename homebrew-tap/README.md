# Homebrew Tap for gstack

This is the official Homebrew tap for [gstack](https://github.com/nicomalacho/stack-branch), a CLI tool for managing stacked Git branches.

## Installation

```bash
brew tap nicomalacho/tap
brew install gstack
```

After installation, use the `gs` command:

```bash
gs --help
```

## Upgrade

```bash
brew upgrade gstack
```

## Uninstall

```bash
brew uninstall gstack
brew untap nicomalacho/tap
```

## What is gstack?

`gstack` (aliased as `gs`) is a CLI tool for managing stacked Git branches with automated rebasing and GitHub PR management. It's inspired by [Graphite](https://graphite.dev/).

Features:
- Create and manage stacked branches
- Automatic rebasing when parent branches change
- GitHub PR creation and management
- Git pass-through for all standard git commands
