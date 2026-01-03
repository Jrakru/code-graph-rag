# Code-Graph-RAG: Monitoring, Setup, and Management Guide

This guide explains how to set up, monitor, and maintain your code-graph-rag knowledge graph system, including Docker services, initial indexing, and realtime file watching.

## Table of Contents

- [Quick Start](#quick-start)
- [Understanding the Components](#understanding-the-components)
- [Setup and Deployment](#setup-and-deployment)
- [Checking Graph Status](#checking-graph-status)
- [Realtime Monitoring](#realtime-monitoring)
- [Docker Management](#docker-management)
- [Troubleshooting](#troubleshooting)
- [Management Script Reference](#management-script-reference)

## Quick Start

### First-Time Setup (All-in-One)

```bash
cd /path/to/code-graph-rag
./manage-graph.sh quick-start /path/to/your/repository
```

This single command will:
1. Install all Python dependencies
2. Start Docker services (Memgraph + Lab)
3. Index your entire repository
4. Begin realtime file watching with sensible defaults

### Subsequent Sessions

After your first setup, on new logins:

```bash
# Terminal 1: Start Docker services
cd /path/to/code-graph-rag
./manage-graph.sh start-docker

# Terminal 2: Start realtime watcher
./manage-graph.sh watch /path/to/your/repository
```

### Check System Health

```bash
./manage-graph.sh status
```

## Understanding the Components

### 1. **Memgraph Database**

The core knowledge graph store. Runs in Docker and persists codebase structure as an interconnected graph.

- **Default Port**: 7687 (database) / 7444 (HTTP/Lab UI)
- **Docker Image**: `memgraph/memgraph-mage`
- **Starts automatically** with `docker-compose up`

### 2. **Initial Indexer** (`cgr start --update-graph`)

One-time process that:
- Scans your entire repository
- Parses all source files using tree-sitter
- Builds the initial knowledge graph
- Takes **5-30 minutes** depending on codebase size

**When to run**: 
- First time setting up for a repository
- After major refactoring/restructuring
- When you suspect the graph is out of sync with source

### 3. **Realtime Watcher** (`realtime_updater.py`)

Continuous process that:
- Monitors file system for changes
- Updates the graph incrementally
- Uses debouncing to batch rapid saves
- Runs **24/7** or until manually stopped

**When to run**:
- During active development
- Whenever you're making code changes
- For continuous synchronization

### 4. **Graph Status / Checking**

There are multiple ways to determine if your graph is up-to-date.

## Setup and Deployment

### Prerequisites

Before you begin, ensure you have:

- **Docker & Docker Compose** - For containerized services
- **Python 3.12+** - For code-graph-rag
- **uv package manager** - For Python dependency management
- **cmake & ripgrep** - For building and searching

Install missing tools:

```bash
# macOS
brew install docker docker-compose cmake ripgrep

# Ubuntu/Debian
sudo apt-get install docker.io docker-compose cmake ripgrep
curl -LsSf https://astral.sh/uv/install.sh | sh

# Start Docker daemon
sudo systemctl start docker
sudo usermod -aG docker $USER  # Add current user to docker group
```

### Step 1: Initial Setup

```bash
cd /path/to/code-graph-rag
./manage-graph.sh setup
```

This installs:
- Python virtual environment with all dependencies
- Tree-sitter language grammars
- Development tools

### Step 2: Start Docker Services

```bash
./manage-graph.sh start-docker
```

Starts:
- Memgraph database (listening on `localhost:7687`)
- Memgraph Lab UI (available at `http://localhost:7444`)

**Verify it's running**:
```bash
curl http://localhost:7444
```

### Step 3: Index Your Repository

```bash
./manage-graph.sh index /path/to/your/repository
```

This performs initial full scan and indexing. Progress is shown in real-time.

**Expected time**: 
- Small projects (< 50k LOC): 5-15 minutes
- Medium projects (50k-500k LOC): 15-45 minutes
- Large projects (> 500k LOC): 45-120+ minutes

### Step 4: Start Realtime Watcher

```bash
./manage-graph.sh watch /path/to/your/repository
```

The watcher will now:
- Monitor for file changes
- Batch rapid saves (debounce)
- Update the graph automatically
- Run until you press Ctrl+C

**With custom timing**:
```bash
# More aggressive batching (10s debounce, 60s max wait)
./manage-graph.sh watch /path/to/your/repository 10 60

# Quick feedback for demos (2s debounce, 10s max wait)
./manage-graph.sh watch /path/to/your/repository 2 10

# Disable batching (0s debounce - legacy behavior)
./manage-graph.sh watch /path/to/your/repository 0 30
```

## Checking Graph Status

### Quick Status Check

```bash
./manage-graph.sh status
```

Output shows:
```
Docker Services:
✓ Memgraph is running on localhost:7687

Python Environment:
✓ Virtual environment exists

Graph Information:
ℹ Checking graph statistics...
Graph is accessible

Realtime Watcher:
✓ Realtime watcher is running (PIDs: 693463,693467)

Recent Activity:
ℹ Latest logs...
```

### Detailed Graph Information

To see actual node/relationship counts:

```bash
# Via CLI (requires Memgraph running)
uv run cgr start --repo-path /path/to/repo

# Via HTTP API
curl http://localhost:7444/api/database/stats

# Via Memgraph Lab UI
open http://localhost:7444
# Navigate to "Query" tab and run Cypher queries
```

### Check if Graph Needs Re-indexing

Your graph likely needs re-indexing if:

1. **Large file deletions**: Deleted files may leave orphaned nodes
2. **Major refactoring**: Class/function renames create duplicates
3. **Suspicious symbols**: Functions/classes that don't match source
4. **Missing recent changes**: Watcher hasn't caught up
5. **Corrupted state**: Graph queries return wrong results

**What to do**:
```bash
# Option 1: Clean and re-index (recommended)
./manage-graph.sh stop-docker
docker-compose down -v  # Delete graph volume
./manage-graph.sh start-docker
./manage-graph.sh index /path/to/repo

# Option 2: Keep existing graph and re-index on top
./manage-graph.sh index /path/to/repo
# (Memgraph will add/update nodes, won't remove orphaned ones)
```

## Realtime Monitoring

### Understanding Debounce Parameters

The realtime watcher uses **two timing strategies**:

1. **Debounce** (default: 5s)
   - Waits for quiet period after last change
   - Batches rapid saves together
   - Reduces redundant processing
   - Good for active development

2. **Max Wait** (default: 30s)
   - Ensures updates happen within maximum window
   - Prevents indefinite delays during continuous editing
   - Guarantees fresh graph within max_wait seconds

**Example**:
- User saves file at `0s`
- User saves again at `2s` → debounce timer resets
- No more changes until `7s` → update runs
- Total time to graph update: ~7s

### Monitoring the Watcher

View watcher logs:
```bash
# List all watcher logs
./manage-graph.sh logs

# Follow latest watcher log
tail -f .logs/watcher-*.log
```

Common log entries:
```
Change detected: modified on models.rs (debouncing for 5.0s)
Scheduled update for models.rs in 5s (max wait: 25s remaining)
Processing debounced change: models.rs
Graph updated successfully for change in: models.rs
```

### Check Running Processes

```bash
# See all graph-rag processes
ps aux | grep -E "(cgr|realtime_updater|memgraph)" | grep -v grep

# Count active watchers
pgrep -f "realtime_updater.py" | wc -l

# Monitor CPU/memory in real-time
watch -n 1 'ps aux | grep realtime_updater'
```

### Watcher Health Indicators

✓ **Healthy**:
- Regular "Change detected" messages
- "Graph updated" confirmations
- No error messages

⚠️ **Needs attention**:
- No activity for > 2 minutes (may have crashed)
- Repeated "Failed to create CALLS relationships" warnings
- High memory usage (> 2GB)

## Docker Management

### View Running Services

```bash
docker-compose ps
```

Expected output:
```
NAME                    STATUS
memgraph                Up (healthy)
memgraph-lab            Up
```

### View Service Logs

```bash
# All services
docker-compose logs

# Follow Memgraph logs
docker-compose logs -f memgraph

# Follow Lab logs
docker-compose logs -f lab
```

### Stop Services

```bash
# Gracefully stop (data persists)
./manage-graph.sh stop-docker

# Or manually
docker-compose down
```

### Delete and Reset Graph (DESTRUCTIVE)

⚠️ **WARNING**: This deletes all indexed data!

```bash
# Stop services and remove volume
docker-compose down -v

# Restart fresh
./manage-graph.sh start-docker
./manage-graph.sh index /path/to/repo
```

### Resource Usage

Check Docker container resources:

```bash
docker stats memgraph

# Or in background
./manage-graph.sh status  # Shows running processes
```

Typical resource usage:
- **Small project** (~50k LOC): 200MB RAM
- **Medium project** (~500k LOC): 1-2GB RAM
- **Large project** (~5M LOC): 3-8GB RAM

If using too much memory, consider:
- Adjusting batch size: `--batch-size 500` (smaller = less RAM)
- Stopping the watcher when not actively developing
- Archiving old indexing data

## Troubleshooting

### Problem: "Memgraph is not running"

```bash
# Check if Docker daemon is running
docker ps

# Start Docker
sudo systemctl start docker    # Linux
open -a Docker                 # macOS

# Start services
./manage-graph.sh start-docker

# Verify
./manage-graph.sh status
```

### Problem: Watcher crashes with "dictionary changed size during iteration"

This is a known issue with concurrent file access. Workaround:

```bash
# Restart watcher with larger debounce
./manage-graph.sh watch /path/to/repo 10 60
```

### Problem: Graph feels stale or missing recent changes

Check if watcher is running:
```bash
pgrep -f "realtime_updater.py"
```

If not running, restart it:
```bash
./manage-graph.sh watch /path/to/repo
```

If running but not updating:
1. Check logs: `./manage-graph.sh logs`
2. Verify Memgraph is healthy: `./manage-graph.sh status`
3. Force re-index: `./manage-graph.sh index /path/to/repo`

### Problem: "CALLS relationships failed" warnings

These warnings indicate some function calls couldn't be linked. This is usually harmless but indicates potential parsing edge cases. To minimize:

1. Ensure all supported languages are installed
2. Update tree-sitter grammars: `git submodule update --init --recursive`
3. Re-index: `./manage-graph.sh index /path/to/repo`

### Problem: Docker port conflicts (7687 or 7444 already in use)

```bash
# Find what's using the port
lsof -i :7687
lsof -i :7444

# Kill the process
kill -9 <PID>

# Or use different port
export MEMGRAPH_PORT=7688
./manage-graph.sh start-docker
```

### Problem: Out of disk space

The graph database can grow large. Check usage:

```bash
docker system df
docker volume ls

# Clean up Docker
docker system prune -a  # WARNING: Removes all unused containers/images
```

## Management Script Reference

### Command: `setup`

Install all dependencies and prepare the environment.

```bash
./manage-graph.sh setup
```

**When to use**: First-time setup or after fresh clone

**What it does**:
- Verifies Docker, Python, uv are installed
- Creates Python virtual environment
- Installs all dependencies with tree-sitter support

### Command: `start-docker`

Start Memgraph and Lab services.

```bash
./manage-graph.sh start-docker
```

**When to use**: After login, before indexing/watching

**Verifies**:
- Docker is running
- Memgraph becomes available on 7687
- Lab UI available at http://localhost:7444

### Command: `stop-docker`

Stop Docker services (data persists).

```bash
./manage-graph.sh stop-docker
```

**When to use**: End of work session, before system restart

**Does NOT delete**: Graph data, indexed information

### Command: `index <REPO_PATH>`

Perform initial full-scan indexing of a repository.

```bash
./manage-graph.sh index /path/to/repository
```

**Parameters**:
- `<REPO_PATH>` - Absolute path to repository (required)

**When to use**:
- First time indexing a new repository
- After major refactoring
- When graph is suspected corrupted

**Options**:
```bash
# Clean index (delete old data first)
# First reset Docker, then index
docker-compose down -v
./manage-graph.sh start-docker
./manage-graph.sh index /path/to/repo
```

### Command: `watch <REPO_PATH> [DEBOUNCE] [MAX_WAIT]`

Start realtime file watcher for continuous updates.

```bash
./manage-graph.sh watch /path/to/repository [debounce_seconds] [max_wait_seconds]
```

**Parameters**:
- `<REPO_PATH>` - Path to monitor (required)
- `[DEBOUNCE]` - Quiet period in seconds (default: 5)
- `[MAX_WAIT]` - Maximum wait in seconds (default: 30)

**Examples**:
```bash
# Default settings (5s debounce, 30s max wait)
./manage-graph.sh watch ~/my-project

# Aggressive batching for background monitoring
./manage-graph.sh watch ~/my-project 10 60

# Quick feedback for demos
./manage-graph.sh watch ~/my-project 2 10

# Disable debouncing (immediate updates)
./manage-graph.sh watch ~/my-project 0 30
```

**When to use**: During active development

**Requirements**:
- Repository must be indexed first
- Memgraph must be running
- Sufficient disk space for graph growth

### Command: `status`

Display current system status and health.

```bash
./manage-graph.sh status
```

**Shows**:
- Docker services status
- Python environment check
- Graph accessibility
- Running realtime watchers
- Recent log activity

**Use regularly** to monitor system health.

### Command: `logs [FILENAME]`

View activity logs.

```bash
# List all available logs
./manage-graph.sh logs

# Follow latest watcher log
./manage-graph.sh logs watcher-20250103-153000.log
```

**Log files location**: `.logs/` directory

**Log types**:
- `watcher-TIMESTAMP.log` - Realtime watcher activity
- System logs from Docker: `docker-compose logs`

### Command: `quick-start <REPO_PATH> [DEBOUNCE] [MAX_WAIT]`

Complete automated setup (setup → docker → index → watch).

```bash
./manage-graph.sh quick-start /path/to/repository [debounce] [max_wait]
```

**When to use**: First-time complete setup

**What it does**:
1. Runs `setup` (install dependencies)
2. Runs `start-docker` (start services)
3. Runs `index` (full scan and indexing)
4. Runs `watch` (starts realtime monitoring)

**Time to completion**: 10-120 minutes depending on repository size

### Command: `help`

Display help and usage information.

```bash
./manage-graph.sh help
```

## Environment Variables

Control behavior via environment variables:

```bash
# Memgraph connection settings
export MEMGRAPH_HOST=localhost          # Default: localhost
export MEMGRAPH_PORT=7687               # Default: 7687
export MEMGRAPH_HTTP_PORT=7444          # Default: 7444

# Then run commands
./manage-graph.sh start-docker
./manage-graph.sh watch /path/to/repo
```

## Best Practices

### Development Workflow

```bash
# Session start
./manage-graph.sh start-docker
./manage-graph.sh watch ~/my-project &

# Work on code...
# Graph updates automatically as you save

# Session end
./manage-graph.sh stop-docker
```

### Large Codebases (> 1M LOC)

1. Use larger debounce/max-wait to reduce overhead:
   ```bash
   ./manage-graph.sh watch /path/to/repo 15 90
   ```

2. Monitor disk/memory usage:
   ```bash
   ./manage-graph.sh status
   docker stats
   ```

3. Consider periodic full re-indexes (weekly):
   ```bash
   docker-compose down -v
   ./manage-graph.sh start-docker
   ./manage-graph.sh index /path/to/repo
   ```

### Multiple Repositories

Use separate Memgraph instances:

```bash
# For each repo, use different port
export MEMGRAPH_PORT=7688
./manage-graph.sh start-docker
./manage-graph.sh index /path/to/repo2

# Watch repo 2
./manage-graph.sh watch /path/to/repo2
```

### Automated Monitoring

Create a startup script:

```bash
#!/bin/bash
# ~/.local/bin/cgr-watch

cd /path/to/code-graph-rag
./manage-graph.sh start-docker
./manage-graph.sh watch /path/to/repository 5 30 >> ~/.logs/cgr-watcher.log 2>&1 &
echo "Graph watcher started in background"
```

Then in your shell profile (`.bashrc` / `.zshrc`):

```bash
# Auto-start graph watcher on login
~/.local/bin/cgr-watch || true  # Don't fail if Docker isn't available
```

## Additional Resources

- **Main README**: See `README.md` for feature overview
- **API Usage**: See `docs/claude-code-setup.md` for MCP integration
- **Configuration**: See `codebase_rag/config.py` for advanced settings
- **Fork Structure**: See `.github/FORK_STRUCTURE.md` for branch management
- **Issues/Bugs**: See `CONTRIBUTING.md` for reporting problems