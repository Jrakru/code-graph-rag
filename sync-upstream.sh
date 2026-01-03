#!/bin/bash
# Upstream Sync Script for code-graph-rag Fork
# Safely syncs upstream changes into your dev branch while preserving local features

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

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

# Check if we're in a git repository
check_git_repo() {
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        print_error "Not a git repository. Run this script from the code-graph-rag directory."
        exit 1
    fi
}

# Check if upstream remote exists
check_upstream_remote() {
    if ! git remote | grep -q "^upstream$"; then
        print_error "Upstream remote not found."
        print_info "Add it with: git remote add upstream https://github.com/vitali87/code-graph-rag.git"
        exit 1
    fi
    print_success "Upstream remote exists"
}

# Check for uncommitted changes
check_clean_working_tree() {
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        print_error "You have uncommitted changes. Please commit or stash them first."
        git status --short
        exit 1
    fi
    print_success "Working tree is clean"
}

# Fetch latest from upstream
fetch_upstream() {
    print_info "Fetching latest from upstream..."
    git fetch upstream
    print_success "Upstream fetched"
}

# Update main branch
update_main() {
    print_info "Updating main branch from upstream..."

    local current_branch=$(git branch --show-current)

    # Switch to main
    git checkout main

    # Get current main commit
    local old_commit=$(git rev-parse HEAD)

    # Pull from upstream
    git pull upstream main

    # Get new main commit
    local new_commit=$(git rev-parse HEAD)

    # Push to origin
    git push origin main

    # Show what changed
    if [ "$old_commit" != "$new_commit" ]; then
        print_success "Main updated: $old_commit → $new_commit"
        echo ""
        print_info "New commits from upstream:"
        git log --oneline --decorate --color "$old_commit..$new_commit" | head -10
        echo ""
    else
        print_success "Main is already up to date"
    fi

    # Return to original branch if it wasn't main
    if [ "$current_branch" != "main" ]; then
        git checkout "$current_branch"
    fi
}

# Merge main into dev
merge_main_into_dev() {
    print_info "Merging main into dev..."

    local current_branch=$(git branch --show-current)

    # Switch to dev
    git checkout dev

    # Check if there are commits to merge
    local commits_behind=$(git rev-list --count dev..main)

    if [ "$commits_behind" -eq 0 ]; then
        print_success "Dev is already up to date with main"
        if [ "$current_branch" != "dev" ]; then
            git checkout "$current_branch"
        fi
        return 0
    fi

    print_info "Dev is $commits_behind commits behind main"
    print_info "Attempting merge..."

    # Try to merge
    if git merge main --no-edit; then
        print_success "Successfully merged main into dev"

        # Push to origin
        git push origin dev
        print_success "Pushed updated dev to origin"

        echo ""
        print_info "Summary:"
        echo -e "  ${GREEN}✓${NC} Merged $commits_behind commits from upstream into dev"
        echo -e "  ${GREEN}✓${NC} Your local features are preserved"
        echo -e "  ${GREEN}✓${NC} Dev branch is now up to date"

    else
        print_error "Merge conflict detected!"
        echo ""
        print_warning "You need to resolve conflicts manually:"
        echo "  1. Fix conflicts in the listed files"
        echo "  2. Stage resolved files: git add <file>"
        echo "  3. Complete merge: git commit"
        echo "  4. Push changes: git push origin dev"
        echo ""
        print_info "To abort merge: git merge --abort"
        exit 1
    fi

    # Return to original branch if it wasn't dev
    if [ "$current_branch" != "dev" ]; then
        git checkout "$current_branch"
    fi
}

# Show sync status
show_status() {
    print_header "SYNC STATUS"

    # Fetch first
    git fetch upstream 2>/dev/null || true
    git fetch origin 2>/dev/null || true

    echo -e "${BOLD}Branches:${NC}"

    # Main status
    local main_behind=$(git rev-list --count main..upstream/main 2>/dev/null || echo "0")
    local main_ahead=$(git rev-list --count upstream/main..main 2>/dev/null || echo "0")

    if [ "$main_behind" -eq 0 ] && [ "$main_ahead" -eq 0 ]; then
        echo -e "  main:  ${GREEN}✓${NC} Synced with upstream"
    elif [ "$main_behind" -gt 0 ]; then
        echo -e "  main:  ${YELLOW}⚠${NC} Behind upstream by $main_behind commits"
    fi

    # Dev status
    local dev_behind=$(git rev-list --count dev..main 2>/dev/null || echo "0")
    local dev_ahead=$(git rev-list --count main..dev 2>/dev/null || echo "0")

    if [ "$dev_behind" -eq 0 ]; then
        echo -e "  dev:   ${GREEN}✓${NC} Up to date with main"
        if [ "$dev_ahead" -gt 0 ]; then
            echo -e "         ${BLUE}ℹ${NC} $dev_ahead local commits ahead"
        fi
    else
        echo -e "  dev:   ${YELLOW}⚠${NC} Behind main by $dev_behind commits"
        if [ "$dev_ahead" -gt 0 ]; then
            echo -e "         ${BLUE}ℹ${NC} $dev_ahead local commits ahead"
        fi
    fi

    echo ""
    echo -e "${BOLD}Local features in dev (not in main):${NC}"
    local feature_count=$(git rev-list --count main..dev 2>/dev/null || echo "0")
    if [ "$feature_count" -gt 0 ]; then
        git log --oneline --decorate --color main..dev | head -10
    else
        echo "  (none)"
    fi

    echo ""
    echo -e "${BOLD}Recommendations:${NC}"

    if [ "$main_behind" -gt 0 ]; then
        echo -e "  ${YELLOW}→${NC} Run: $0 sync"
    elif [ "$dev_behind" -gt 0 ]; then
        echo -e "  ${YELLOW}→${NC} Run: $0 sync"
    else
        echo -e "  ${GREEN}✓${NC} Everything is up to date!"
    fi
}

# Full sync (main + dev)
full_sync() {
    print_header "SYNCING WITH UPSTREAM"

    check_git_repo
    check_upstream_remote
    check_clean_working_tree

    fetch_upstream
    update_main
    merge_main_into_dev

    print_header "SYNC COMPLETE"
    print_success "Your dev branch now includes latest upstream changes"
    print_success "Your local features are preserved"
    echo ""
    print_info "Next steps:"
    echo "  - Test your local features with the new upstream changes"
    echo "  - Run your test suite to ensure compatibility"
    echo "  - If you have feature branches, rebase them on dev:"
    echo "    git checkout feature/my-feature"
    echo "    git rebase dev"
}

# Dry run - show what would happen
dry_run() {
    print_header "DRY RUN - SYNC PREVIEW"

    check_git_repo
    check_upstream_remote

    git fetch upstream 2>/dev/null

    local main_behind=$(git rev-list --count main..upstream/main 2>/dev/null || echo "0")
    local dev_behind=$(git rev-list --count dev..main 2>/dev/null || echo "0")

    echo -e "${BOLD}What will happen:${NC}"
    echo ""

    if [ "$main_behind" -gt 0 ]; then
        echo -e "${BLUE}1.${NC} Update main:"
        echo "   - Pull $main_behind new commits from upstream"
        echo "   - Push updated main to origin"
        echo ""
        print_info "New commits to be pulled:"
        git log --oneline --decorate --color main..upstream/main | head -10
        echo ""
    else
        echo -e "${BLUE}1.${NC} Update main:"
        echo "   - Already up to date"
        echo ""
    fi

    if [ "$dev_behind" -gt 0 ]; then
        echo -e "${BLUE}2.${NC} Merge main into dev:"
        echo "   - Merge $dev_behind commits from main"
        echo "   - Preserve all local features in dev"
        echo "   - Push updated dev to origin"
        echo ""

        # Check for potential conflicts
        git checkout dev 2>/dev/null
        if ! git merge-tree $(git merge-base dev main) main dev | grep -q "^added in both"; then
            print_success "No merge conflicts detected"
        else
            print_warning "Potential merge conflicts detected - manual resolution may be needed"
        fi
        git checkout - 2>/dev/null
        echo ""
    else
        echo -e "${BLUE}2.${NC} Merge main into dev:"
        echo "   - Already up to date"
        echo ""
    fi

    local feature_count=$(git rev-list --count main..dev 2>/dev/null || echo "0")
    echo -e "${BOLD}Your local features (will be preserved):${NC}"
    if [ "$feature_count" -gt 0 ]; then
        echo "   $feature_count commits ahead of main"
    else
        echo "   (none)"
    fi

    echo ""
    print_info "To proceed with sync, run: $0 sync"
}

# Help message
show_help() {
    cat << 'EOF'
╔════════════════════════════════════════════════════════════════════════════╗
║                    Upstream Sync Script for code-graph-rag                 ║
║              Safely integrate upstream changes into your dev branch        ║
╚════════════════════════════════════════════════════════════════════════════╝

USAGE:
  ./sync-upstream.sh <COMMAND>

COMMANDS:

  sync
    Perform full sync: update main from upstream, merge main into dev
    - Fetches latest upstream changes
    - Updates main to match upstream/main
    - Merges main into dev (preserving local features)
    - Pushes both main and dev to origin
    Usage: ./sync-upstream.sh sync

  status
    Show current sync status
    - Check if main is up to date with upstream
    - Check if dev is up to date with main
    - Show local features in dev (commits ahead of main)
    - Provide recommendations
    Usage: ./sync-upstream.sh status

  dry-run
    Preview what sync would do without making changes
    - Show commits that would be pulled
    - Check for potential merge conflicts
    - Show what will be preserved
    Usage: ./sync-upstream.sh dry-run

  update-main
    Only update main branch from upstream (without touching dev)
    Usage: ./sync-upstream.sh update-main

  merge-to-dev
    Only merge main into dev (assumes main is already updated)
    Usage: ./sync-upstream.sh merge-to-dev

  help
    Show this help message
    Usage: ./sync-upstream.sh help

WORKFLOW:

  Development cycle with upstream sync:

  1. Develop features:
     $ git checkout -b feature/my-feature dev
     $ # ... work ...
     $ git push origin feature/my-feature
     $ # Create PR: feature/my-feature → dev

  2. Periodically sync upstream (weekly/monthly):
     $ ./sync-upstream.sh status          # Check what's new
     $ ./sync-upstream.sh dry-run         # Preview changes
     $ ./sync-upstream.sh sync            # Do the sync

  3. Update feature branches after sync:
     $ git checkout feature/my-feature
     $ git rebase dev                     # Rebase on updated dev
     $ git push --force-with-lease origin feature/my-feature

SYNC STRATEGY:

  upstream/main
       ↓ (sync)
  origin/main
       ↓ (merge)
  origin/dev ← Your local features
       ↓ (branch from)
  feature/*

  - main always mirrors upstream (read-only)
  - dev accumulates your local features
  - Upstream changes are merged into dev regularly
  - Feature branches are rebased on dev after sync

CONFLICT RESOLUTION:

  If merge conflicts occur during sync:

  1. Script will stop and show conflicted files
  2. Manually resolve conflicts in each file
  3. Stage resolved files: git add <file>
  4. Complete merge: git commit
  5. Push to origin: git push origin dev

  Or abort: git merge --abort

BEST PRACTICES:

  ✓ Run 'sync' at regular intervals (weekly/monthly)
  ✓ Always check 'status' before syncing
  ✓ Use 'dry-run' to preview changes
  ✓ Commit/stash local changes before syncing
  ✓ Test your features after syncing
  ✓ Rebase feature branches on updated dev

TROUBLESHOOTING:

  "You have uncommitted changes"
  → Commit or stash: git stash

  "Merge conflict detected"
  → Resolve manually, then: git add . && git commit

  "Upstream remote not found"
  → Add it: git remote add upstream https://github.com/vitali87/code-graph-rag.git

EXAMPLES:

  # Check current sync status
  ./sync-upstream.sh status

  # Preview what would happen
  ./sync-upstream.sh dry-run

  # Perform full sync
  ./sync-upstream.sh sync

  # Only update main (skip dev merge)
  ./sync-upstream.sh update-main

EOF
}

# Main entrypoint
main() {
    cd "$SCRIPT_DIR"

    local command="${1:-help}"

    case "$command" in
        sync)
            full_sync
            ;;
        status)
            show_status
            ;;
        dry-run|preview)
            dry_run
            ;;
        update-main)
            check_git_repo
            check_upstream_remote
            check_clean_working_tree
            fetch_upstream
            update_main
            ;;
        merge-to-dev)
            check_git_repo
            check_clean_working_tree
            merge_main_into_dev
            ;;
        help|-h|--help)
            show_help
            ;;
        *)
            print_error "Unknown command: $command"
            echo ""
            show_help
            exit 1
            ;;
    esac
}

main "$@"
