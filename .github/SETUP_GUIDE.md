# Code-Graph-RAG Fork Setup Guide

Welcome! This guide explains how to use this fork of code-graph-rag with proper branch structure and local development practices.

## Quick Overview

This fork maintains:
- **`main`** - Mirror of upstream (vitali87/code-graph-rag)
- **`dev`** - Your local development base (for local features)
- **`feature/*`** - Individual feature branches

## First-Time Setup

### 1. Clone and Configure Remotes

```bash
git clone https://github.com/Jrakru/code-graph-rag.git
cd code-graph-rag

# Add upstream remote (if not already present)
git remote add upstream https://github.com/vitali87/code-graph-rag.git

# Verify remotes
git remote -v
# origin    https://github.com/Jrakru/code-graph-rag.git (your fork)
# upstream  https://github.com/vitali87/code-graph-rag.git (original)
```

### 2. Checkout Development Branch

```bash
# Use the dev branch for all local work
git checkout dev

# Or create it if it doesn't exist
git checkout -b dev origin/dev
```

### 3. Install Dependencies

```bash
./manage-graph.sh setup
```

This installs:
- Python environment with all dependencies
- Tree-sitter language support
- Development tools

## Using the Management Script

The `manage-graph.sh` script handles all setup and monitoring tasks:

### First-Time Complete Setup

```bash
./manage-graph.sh quick-start /path/to/repository
```

This does everything in one command:
1. Installs dependencies
2. Starts Docker services (Memgraph)
3. Indexes your repository
4. Starts realtime file watching

### Subsequent Sessions

```bash
# Terminal 1: Start Docker
./manage-graph.sh start-docker

# Terminal 2: Start watching (after first-time index)
./manage-graph.sh watch /path/to/repository
```

### Monitor Your System

```bash
# Check status anytime
./manage-graph.sh status

# View logs
./manage-graph.sh logs
```

## Branch Workflow

### Starting a New Feature

```bash
# Make sure you're on dev with latest code
git checkout dev
git pull origin dev

# Create a feature branch
git checkout -b feature/my-feature dev
git push origin feature/my-feature
```

### Making Changes

```bash
git commit -am "describe your change"
git push origin feature/my-feature
```

### Creating a Pull Request

1. Go to GitHub
2. Create PR: `feature/my-feature` → `dev` (not main!)
3. Have it reviewed
4. Merge into dev

After merge:
```bash
git checkout dev
git pull origin dev
git branch -d feature/my-feature
git push origin --delete feature/my-feature
```

### Syncing with Upstream

When upstream has new changes:

```bash
# Update main from upstream
git fetch upstream
git checkout main
git pull upstream main
git push origin main

# Rebase dev on the new main
git checkout dev
git rebase main
git push origin dev
```

## Common Tasks

### "I want to check if the graph needs re-indexing"

```bash
./manage-graph.sh status
```

Signs your graph needs re-indexing:
- Missing recent code changes
- Orphaned symbols after file deletions
- Unexpected query results

To re-index:
```bash
./manage-graph.sh stop-docker
docker-compose down -v  # Delete old data
./manage-graph.sh start-docker
./manage-graph.sh index /path/to/repo
./manage-graph.sh watch /path/to/repo
```

### "How do I know if the watcher is running?"

```bash
./manage-graph.sh status
```

Or check manually:
```bash
pgrep -f "realtime_updater.py"
```

### "My feature is ready to send upstream"

Option 1: Direct GitHub PR
```bash
# On feature/my-feature
# Go to GitHub and create PR to vitali87/main
```

Option 2: Cherry-pick to clean branch
```bash
git checkout -b feature/upstream-ready main
git cherry-pick feature/my-feature...
git push origin feature/upstream-ready
# Create PR on GitHub to vitali87/main
```

### "I want to test a feature without committing"

```bash
git checkout dev
git merge feature/my-feature
# ... test ...
git reset --hard origin/dev  # Undo merge
```

### "I want to update dev with latest main"

```bash
git fetch upstream
git checkout main
git pull upstream main
git push origin main

git checkout dev
git merge main
git push origin dev
```

## Understanding the Debounce Feature

The realtime watcher batches file changes to prevent redundant graph updates:

```bash
# Default (sensible for most development)
./manage-graph.sh watch /path/to/repo

# More aggressive batching (background monitoring)
./manage-graph.sh watch /path/to/repo 10 60

# Quick feedback (demos)
./manage-graph.sh watch /path/to/repo 2 10

# Disable batching (legacy behavior)
./manage-graph.sh watch /path/to/repo 0 30
```

Parameters:
- **Debounce** (1st number): Wait this long after last change before updating
- **Max Wait** (2nd number): Force update after this long, even if changes continue

## Repository Layout

```
.
├── .github/
│   ├── FORK_STRUCTURE.md       ← Detailed branch strategy
│   └── SETUP_GUIDE.md          ← This file
├── manage-graph.sh             ← Main management tool
├── docs/
│   ├── MONITORING_AND_SETUP.md ← Comprehensive operations guide
│   └── claude-code-setup.md
├── realtime_updater.py         ← Realtime file watcher
├── codebase_rag/
│   ├── cli.py                  ← Main CLI entry point
│   └── ...
└── docker-compose.yaml
```

## Key Files

- **`manage-graph.sh`** - Everything you need for setup and monitoring
- **`.github/FORK_STRUCTURE.md`** - Detailed branch management strategy
- **`docs/MONITORING_AND_SETUP.md`** - Complete operations guide
- **`realtime_updater.py`** - Realtime file watcher with debouncing

## Troubleshooting

### Docker won't start

```bash
# Check if Docker daemon is running
docker ps

# Start Docker
sudo systemctl start docker    # Linux
open -a Docker                 # macOS
```

### Port already in use

```bash
# Check what's using port 7687
lsof -i :7687

# Use different port
export MEMGRAPH_PORT=7688
./manage-graph.sh start-docker
```

### Watcher crashes

```bash
# Restart with larger debounce
./manage-graph.sh watch /path/to/repo 10 60
```

### Graph feels stale

```bash
# Check if watcher is running
./manage-graph.sh status

# View recent activity
./manage-graph.sh logs
```

## Getting Help

1. **For deployment/monitoring**: See `docs/MONITORING_AND_SETUP.md`
2. **For branch strategy**: See `.github/FORK_STRUCTURE.md`
3. **For management script commands**: Run `./manage-graph.sh help`
4. **For contributing**: See `CONTRIBUTING.md`

## Key Principles

1. **Never commit to `main`** - It's just a mirror of upstream
2. **Always work in `dev`** - Create feature branches from dev
3. **Sync frequently** - Pull upstream changes often to avoid conflicts
4. **Test before merging** - Always verify features work
5. **Delete feature branches** - Clean up after merging
6. **Use the management script** - It handles all the complexity

## Next Steps

1. Run: `./manage-graph.sh quick-start /path/to/your/repository`
2. Check status: `./manage-graph.sh status`
3. Start developing!

Welcome to the team! 🚀