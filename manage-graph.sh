#!/bin/bash
# Code-Graph-RAG Management Script
# Comprehensive setup, monitoring, and management of the code graph system
# Handles Docker services, initial indexing, realtime watching, and status checks

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/.logs"
PID_FILE="${LOG_DIR}/cgr-manager.pid"
DOCKER_COMPOSE_FILE="${SCRIPT_DIR}/docker-compose.yaml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default values
MEMGRAPH_HOST="${MEMGRAPH_HOST:-localhost}"
MEMGRAPH_PORT="${MEMGRAPH_PORT:-7687}"
MEMGRAPH_HTTP_PORT="${MEMGRAPH_HTTP_PORT:-7444}"
DEFAULT_DEBOUNCE=5
DEFAULT_MAX_WAIT=30

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

print_header() {
    echo -e "\n${CYAN}${BOLD}╔═══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}${BOLD}║ $1${NC}"
    echo -e "${CYAN}${BOLD}╚═══════════════════════════════════════════════════════════════╝${NC}\n"
}

print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

check_docker() {
    if ! command -v docker &> /dev/null; then
        print_error "Docker is not installed. Please install Docker to use this script."
        return 1
    fi

    if ! docker info &> /dev/null; then
        print_error "Docker daemon is not running. Please start Docker."
        return 1
    fi

    print_success "Docker is running"
    return 0
}

check_docker_compose() {
    if ! command -v docker-compose &> /dev/null; then
        print_error "Docker Compose is not installed. Please install Docker Compose."
        return 1
    fi

    print_success "Docker Compose is available"
    return 0
}

check_python() {
    if ! command -v python3 &> /dev/null; then
        print_error "Python 3 is not installed."
        return 1
    fi

    print_success "Python 3 is available"
    return 0
}

check_uv() {
    if ! command -v uv &> /dev/null; then
        print_error "uv is not installed. Install with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        return 1
    fi

    print_success "uv is available"
    return 0
}

check_memgraph_running() {
    if timeout 2 bash -c "echo > /dev/tcp/$MEMGRAPH_HOST/$MEMGRAPH_PORT" 2>/dev/null; then
        return 0
    fi
    return 1
}

wait_for_memgraph() {
    local max_attempts=30
    local attempt=0

    print_info "Waiting for Memgraph to be ready..."

    while [ $attempt -lt $max_attempts ]; do
        if check_memgraph_running; then
            print_success "Memgraph is ready"
            return 0
        fi

        echo -n "."
        sleep 1
        ((attempt++))
    done

    print_error "Memgraph failed to start after ${max_attempts}s"
    return 1
}

get_graph_stats() {
    local query="MATCH (n) RETURN count(DISTINCT labels(n)) as label_count, count(n) as total_nodes; MATCH ()-[r]->() RETURN count(DISTINCT type(r)) as rel_types, count(r) as total_relationships;"

    if check_memgraph_running; then
        python3 -c "
import socket
import sys

try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect(('$MEMGRAPH_HOST', $MEMGRAPH_PORT))
    s.close()
    print('Graph is accessible')
except Exception as e:
    print(f'Graph is not accessible: {e}')
    sys.exit(1)
" 2>/dev/null || echo "Graph status: unreachable"
    else
        echo "Memgraph is not running"
    fi
}

# =============================================================================
# COMMAND: SETUP
# =============================================================================

cmd_setup() {
    print_header "SETTING UP CODE-GRAPH-RAG"

    print_info "Checking prerequisites..."
    check_docker || return 1
    check_docker_compose || return 1
    check_python || return 1
    check_uv || return 1

    print_info "Installing Python dependencies..."
    cd "$SCRIPT_DIR"
    uv sync --extra treesitter-full --extra test || {
        print_error "Failed to install dependencies"
        return 1
    }

    print_success "All prerequisites installed successfully"
}

# =============================================================================
# COMMAND: START-DOCKER
# =============================================================================

cmd_start_docker() {
    print_header "STARTING DOCKER SERVICES"

    check_docker || return 1
    check_docker_compose || return 1

    cd "$SCRIPT_DIR"

    print_info "Starting Memgraph and Lab services..."
    docker-compose up -d

    if wait_for_memgraph; then
        print_success "Docker services are running"
        print_info "Memgraph API: http://${MEMGRAPH_HOST}:${MEMGRAPH_HTTP_PORT}"
        print_info "Memgraph port: ${MEMGRAPH_HOST}:${MEMGRAPH_PORT}"
        return 0
    else
        print_error "Docker services failed to start properly"
        docker-compose logs
        return 1
    fi
}

# =============================================================================
# COMMAND: STOP-DOCKER
# =============================================================================

cmd_stop_docker() {
    print_header "STOPPING DOCKER SERVICES"

    cd "$SCRIPT_DIR"
    docker-compose down

    print_success "Docker services stopped"
}

# =============================================================================
# COMMAND: INDEX
# =============================================================================

cmd_index() {
    local repo_path="$1"

    if [ -z "$repo_path" ]; then
        print_error "Usage: $0 index <REPO_PATH>"
        return 1
    fi

    if [ ! -d "$repo_path" ]; then
        print_error "Repository path does not exist: $repo_path"
        return 1
    fi

    print_header "INDEXING REPOSITORY"
    print_info "Repository: $repo_path"

    if ! check_memgraph_running; then
        print_error "Memgraph is not running. Start it with: $0 start-docker"
        return 1
    fi

    cd "$SCRIPT_DIR"

    print_info "Starting initial graph indexing..."
    uv run cgr start --repo-path "$repo_path" --update-graph --clean

    if [ $? -eq 0 ]; then
        print_success "Repository indexed successfully"
        return 0
    else
        print_error "Indexing failed"
        return 1
    fi
}

# =============================================================================
# COMMAND: WATCH
# =============================================================================

cmd_watch() {
    local repo_path="$1"
    local debounce="${2:-$DEFAULT_DEBOUNCE}"
    local max_wait="${3:-$DEFAULT_MAX_WAIT}"
    local log_file="${LOG_DIR}/watcher-$(date +%Y%m%d-%H%M%S).log"

    if [ -z "$repo_path" ]; then
        print_error "Usage: $0 watch <REPO_PATH> [DEBOUNCE_SECONDS] [MAX_WAIT_SECONDS]"
        return 1
    fi

    if [ ! -d "$repo_path" ]; then
        print_error "Repository path does not exist: $repo_path"
        return 1
    fi

    print_header "STARTING REALTIME WATCHER"
    print_info "Repository: $repo_path"
    print_info "Debounce: ${debounce}s"
    print_info "Max wait: ${max_wait}s"
    print_info "Log file: $log_file"

    if ! check_memgraph_running; then
        print_error "Memgraph is not running. Start it with: $0 start-docker"
        return 1
    fi

    cd "$SCRIPT_DIR"

    # Check if graph is indexed
    if [ ! -f "${LOG_DIR}/.indexed-${repo_path//\//-}" ]; then
        print_warning "Repository does not appear to be indexed yet."
        print_info "Run: $0 index \"$repo_path\""
        return 1
    fi

    print_info "Starting realtime watcher (press Ctrl+C to stop)..."
    uv run python realtime_updater.py "$repo_path" \
        --host "$MEMGRAPH_HOST" \
        --port "$MEMGRAPH_PORT" \
        --debounce "$debounce" \
        --max-wait "$max_wait" \
        2>&1 | tee "$log_file"
}

# =============================================================================
# COMMAND: STATUS
# =============================================================================

cmd_status() {
    print_header "GRAPH STATUS"

    # Docker status
    echo -e "${BOLD}Docker Services:${NC}"
    if check_memgraph_running; then
        print_success "Memgraph is running on ${MEMGRAPH_HOST}:${MEMGRAPH_PORT}"
    else
        print_warning "Memgraph is not running"
    fi

    # Python environment
    echo -e "\n${BOLD}Python Environment:${NC}"
    if cd "$SCRIPT_DIR" 2>/dev/null && [ -d .venv ]; then
        print_success "Virtual environment exists"
    else
        print_warning "Virtual environment not found. Run: $0 setup"
    fi

    # Graph size
    echo -e "\n${BOLD}Graph Information:${NC}"
    if check_memgraph_running; then
        print_info "Checking graph statistics..."
        get_graph_stats
    else
        print_warning "Cannot access graph - Memgraph is not running"
    fi

    # Realtime watcher status
    echo -e "\n${BOLD}Realtime Watcher:${NC}"
    if pgrep -f "realtime_updater.py" > /dev/null; then
        local pids=$(pgrep -f "realtime_updater.py" | tr '\n' ', ' | sed 's/,$//')
        print_success "Realtime watcher is running (PIDs: $pids)"
    else
        print_info "Realtime watcher is not running"
    fi

    # Recent logs
    echo -e "\n${BOLD}Recent Activity:${NC}"
    if [ -d "$LOG_DIR" ] && [ "$(ls -1 "$LOG_DIR" | wc -l)" -gt 0 ]; then
        print_info "Latest logs:"
        ls -1t "$LOG_DIR"/* 2>/dev/null | head -5 | while read -r log; do
            echo "  $(basename "$log")"
        done
    else
        print_info "No logs found yet"
    fi
}

# =============================================================================
# COMMAND: LOGS
# =============================================================================

cmd_logs() {
    local log_type="${1:-all}"

    print_header "VIEWING LOGS"

    if [ "$log_type" = "all" ]; then
        print_info "All logs in $LOG_DIR:"
        ls -lh "$LOG_DIR"/ 2>/dev/null || echo "No logs found"
    elif [ -f "$LOG_DIR/$log_type" ]; then
        tail -f "$LOG_DIR/$log_type"
    else
        print_error "Log file not found: $log_type"
        print_info "Available logs:"
        ls -1 "$LOG_DIR"/ 2>/dev/null || echo "No logs found"
        return 1
    fi
}

# =============================================================================
# COMMAND: QUICK-START
# =============================================================================

cmd_quick_start() {
    local repo_path="$1"
    local debounce="${2:-$DEFAULT_DEBOUNCE}"
    local max_wait="${3:-$DEFAULT_MAX_WAIT}"

    if [ -z "$repo_path" ]; then
        print_error "Usage: $0 quick-start <REPO_PATH> [DEBOUNCE_SECONDS] [MAX_WAIT_SECONDS]"
        return 1
    fi

    print_header "QUICK START - FULL SETUP"
    print_info "This will:"
    print_info "  1. Setup dependencies"
    print_info "  2. Start Docker services"
    print_info "  3. Index the repository"
    print_info "  4. Start realtime watcher"

    # Setup
    cmd_setup || return 1

    # Start Docker
    cmd_start_docker || return 1

    # Index
    cmd_index "$repo_path" || return 1

    # Mark as indexed
    mkdir -p "$LOG_DIR"
    touch "${LOG_DIR}/.indexed-${repo_path//\//-}"

    # Watch
    cmd_watch "$repo_path" "$debounce" "$max_wait"
}

# =============================================================================
# COMMAND: HELP
# =============================================================================

cmd_help() {
    cat << 'EOF'
╔════════════════════════════════════════════════════════════════════════════╗
║                    Code-Graph-RAG Management Script                        ║
║                  Manage your codebase knowledge graph                      ║
╚════════════════════════════════════════════════════════════════════════════╝

USAGE:
  ./manage-graph.sh <COMMAND> [OPTIONS]

COMMANDS:

  setup
    Setup all dependencies and Python environment
    Usage: ./manage-graph.sh setup

  start-docker
    Start Memgraph and Lab services via Docker Compose
    Usage: ./manage-graph.sh start-docker

  stop-docker
    Stop all Docker services
    Usage: ./manage-graph.sh stop-docker

  index <REPO_PATH>
    Initial graph indexing of a repository
    Usage: ./manage-graph.sh index /path/to/repository

  watch <REPO_PATH> [DEBOUNCE] [MAX_WAIT]
    Start realtime file watcher for continuous graph updates
    - REPO_PATH: Path to repository to watch (required)
    - DEBOUNCE: Debounce delay in seconds (default: 5)
    - MAX_WAIT: Maximum wait time in seconds (default: 30)
    Usage: ./manage-graph.sh watch /path/to/repository 5 30

  status
    Show current status of the entire system
    - Docker services
    - Python environment
    - Graph statistics
    - Running processes
    Usage: ./manage-graph.sh status

  logs [FILENAME]
    View logs from the log directory
    Usage: ./manage-graph.sh logs              # List all logs
    Usage: ./manage-graph.sh logs watcher.log  # Tail specific log

  quick-start <REPO_PATH> [DEBOUNCE] [MAX_WAIT]
    Complete setup from scratch (setup → docker → index → watch)
    Usage: ./manage-graph.sh quick-start /path/to/repository 5 30

  help
    Show this help message
    Usage: ./manage-graph.sh help

TYPICAL WORKFLOW:

  1. First time setup:
     ./manage-graph.sh quick-start /path/to/repository

  2. On subsequent logins (if services stopped):
     ./manage-graph.sh start-docker
     ./manage-graph.sh watch /path/to/repository

  3. Check system health:
     ./manage-graph.sh status

ENVIRONMENT VARIABLES:

  MEMGRAPH_HOST     Memgraph host (default: localhost)
  MEMGRAPH_PORT     Memgraph port (default: 7687)
  MEMGRAPH_HTTP_PORT Memgraph HTTP port for Lab (default: 7444)

LOGS:

  All activity is logged to: .logs/
  Recent logs shown in 'status' command

EXAMPLES:

  # Setup everything for the first time
  ./manage-graph.sh quick-start ~/my-project

  # Start services on a new session
  ./manage-graph.sh start-docker
  ./manage-graph.sh watch ~/my-project 10 60

  # Check what's running
  ./manage-graph.sh status

  # View latest logs
  ./manage-graph.sh logs

EOF
}

# =============================================================================
# MAIN ENTRYPOINT
# =============================================================================

main() {
    local command="${1:-help}"

    case "$command" in
        setup)
            cmd_setup
            ;;
        start-docker|start)
            cmd_start_docker
            ;;
        stop-docker|stop)
            cmd_stop_docker
            ;;
        index)
            cmd_index "$2"
            ;;
        watch)
            cmd_watch "$2" "$3" "$4"
            ;;
        status)
            cmd_status
            ;;
        logs)
            cmd_logs "$2"
            ;;
        quick-start)
            cmd_quick_start "$2" "$3" "$4"
            ;;
        help|-h|--help)
            cmd_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            cmd_help
            exit 1
            ;;
    esac
}

main "$@"
