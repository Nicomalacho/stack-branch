# Homebrew Tap for gs (gstack)

This is the official Homebrew tap for [gs](https://github.com/nicomalacho/stack-branch), a CLI tool for managing stacked Git branches.

## Installation

```bash
brew tap nicomalacho/tap
brew install gs
```

## Upgrade

```bash
brew upgrade gs
```

## Uninstall

```bash
brew uninstall gs
brew untap nicomalacho/tap
```

## What is gs?

`gs` is a CLI tool for managing stacked Git branches with automated rebasing and GitHub PR management. It's inspired by [Graphite](https://graphite.dev/).

Features:
- Create and manage stacked branches
- Automatic rebasing when parent branches change
- GitHub PR creation and management
- Git pass-through for all standard git commands
