# Upstream Sync Guide: Keeping Your Fork Up-to-Date

This guide explains how to continuously pull changes from upstream (vitali87/code-graph-rag) while developing your own features in the `dev` branch.

## Overview

Your fork uses a **merge-based integration strategy** that allows you to:

1. ✅ Develop features continuously in `dev` branch
2. ✅ Pull upstream changes whenever needed
3. ✅ Keep your local features intact
4. ✅ Maintain a clean history showing integration points

## Branch Strategy

```
upstream/main (vitali87's repository)
     ↓
  [sync]
     ↓
origin/main (your mirror, read-only)
     ↓
  [merge]
     ↓
origin/dev (your integration branch)
     ↑
  [merge]
     ↑
feature/* branches (your features)
```

### Branch Roles

| Branch | Purpose | Who Commits |
|--------|---------|-------------|
| `origin/main` | Mirror of upstream | Nobody (sync only) |
| `origin/dev` | Your integration branch | You (merge features) |
| `feature/*` | Individual features | You (develop) |

## The Sync Script

We provide `sync-upstream.sh` to automate the sync process.

### Basic Commands

```bash
# Check current sync status
./sync-upstream.sh status

# Preview what would happen (no changes)
./sync-upstream.sh dry-run

# Perform full sync
./sync-upstream.sh sync
```

## Typical Workflow

### Daily/Weekly Development

```bash
# 1. Create feature branch from dev
git checkout dev
git pull origin dev
git checkout -b feature/my-awesome-feature dev

# 2. Develop your feature
git commit -am "implement awesome feature"
git push origin feature/my-awesome-feature

# 3. Create PR on GitHub: feature/my-awesome-feature → dev
# 4. After review, merge to dev
# 5. Delete feature branch
```

### Monthly Upstream Sync

Every few weeks or when you know upstream has changes you want:

```bash
# 1. Check what's new upstream
./sync-upstream.sh status

# Output shows:
#   Branches:
#     main:  ⚠ Behind upstream by 15 commits
#     dev:   ⚠ Behind main by 15 commits
#            ℹ 8 local commits ahead

# 2. Preview the changes
./sync-upstream.sh dry-run

# Shows:
#   - New commits from upstream
#   - Potential conflicts (if any)
#   - Your local features (will be preserved)

# 3. Perform the sync
./sync-upstream.sh sync

# This does:
#   ✓ Updates main from upstream
#   ✓ Merges main into dev
#   ✓ Preserves all your local features
#   ✓ Pushes both branches to origin
```

### After Sync: Update Feature Branches

If you have active feature branches, rebase them on the updated dev:

```bash
# For each active feature branch
git checkout feature/my-feature
git rebase dev
git push --force-with-lease origin feature/my-feature
```

## Sync Strategy Explained

### Why Merge Instead of Rebase?

We use **merge** (not rebase) to integrate upstream changes because:

1. **Safe**: No force pushes needed on `dev`
2. **History**: Clear record of when upstream was integrated
3. **Collaboration**: Multiple people can work on dev safely
4. **Conflicts**: Easier to resolve conflicts incrementally

### What Happens During Sync?

```bash
# Before sync
main:  commit A (synced with upstream)
dev:   commit A → B → C → D (your features)

# Upstream adds commits E, F, G
upstream/main: commit A → E → F → G

# After sync
main:  commit A → E → F → G (updated)
dev:   commit A → B → C → D → [merge E,F,G] (integrated)
```

Your commits B, C, D are **preserved**. The merge commit shows the integration point.

## Handling Conflicts

If upstream changes conflict with your local features:

### During Sync

```bash
./sync-upstream.sh sync

# Output:
#   ✗ Merge conflict detected!
#   
#   You need to resolve conflicts manually:
#     1. Fix conflicts in the listed files
#     2. Stage resolved files: git add <file>
#     3. Complete merge: git commit
#     4. Push changes: git push origin dev
```

### Resolution Steps

```bash
# 1. Check which files have conflicts
git status

# Output:
#   both modified: codebase_rag/cli.py
#   both modified: README.md

# 2. Open each file and resolve conflicts
#    Look for conflict markers:
#    <<<<<<< HEAD (your changes)
#    =======
#    >>>>>>> main (upstream changes)

# 3. Edit to combine both changes appropriately

# 4. Stage resolved files
git add codebase_rag/cli.py README.md

# 5. Complete the merge
git commit -m "Merge main into dev - resolved conflicts"

# 6. Push to origin
git push origin dev
```

### Aborting a Merge

If you want to start over:

```bash
git merge --abort
```

## Best Practices

### 1. Sync Regularly

```bash
# Don't wait too long between syncs
# Recommended: every 2-4 weeks or when upstream has major updates
./sync-upstream.sh status  # Check weekly
./sync-upstream.sh sync    # Sync when needed
```

### 2. Clean Working Tree

Always commit or stash before syncing:

```bash
# Option 1: Commit
git commit -am "WIP: feature in progress"

# Option 2: Stash
git stash
./sync-upstream.sh sync
git stash pop
```

### 3. Test After Sync

```bash
# After syncing, test your features
./sync-upstream.sh sync

# Run tests
make test

# Test your features manually
./manage-graph.sh quick-start /path/to/repo
```

### 4. Document Integration

When resolving conflicts, document your decisions:

```bash
git commit -m "Merge main into dev

Resolved conflicts in cli.py:
- Kept our custom --batch-size flag
- Adopted upstream's new --verbose flag
- Combined both help text improvements"
```

## Sync Frequency

| Scenario | Recommended Frequency |
|----------|----------------------|
| Active upstream development | Weekly check, monthly sync |
| Stable upstream | Monthly check, quarterly sync |
| Before major release | Always sync first |
| After upstream adds feature you need | Immediately |

## Common Scenarios

### Scenario 1: Quick Check

```bash
# Just want to see if there's anything new?
./sync-upstream.sh status

# No action needed if output shows:
#   ✓ Everything is up to date!
```

### Scenario 2: Preview Before Sync

```bash
# Want to see what would change before committing?
./sync-upstream.sh dry-run

# Review the output carefully
# Then decide whether to proceed
./sync-upstream.sh sync
```

### Scenario 3: Urgent Upstream Fix

```bash
# Upstream fixed a critical bug you need NOW

# 1. Sync immediately
./sync-upstream.sh sync

# 2. Test the fix
make test

# 3. Update any affected feature branches
git checkout feature/related-feature
git rebase dev
```

### Scenario 4: Your Feature Was Merged Upstream

```bash
# Your PR was merged to upstream!
# Now you have duplicate commits

# 1. Sync (the merge commit will handle duplicates)
./sync-upstream.sh sync

# 2. Git is smart enough to recognize identical changes
# The merge will skip your duplicate commits

# 3. Optionally, clean up your dev branch later
# (Remove your original commits since they're now in main)
```

## Manual Sync (Without Script)

If you prefer to sync manually:

```bash
# 1. Update main
git fetch upstream
git checkout main
git pull upstream main
git push origin main

# 2. Merge main into dev
git checkout dev
git merge main

# 3. If conflicts, resolve them:
git add <resolved-files>
git commit

# 4. Push dev
git push origin dev
```

## Troubleshooting

### "Upstream remote not found"

```bash
# Add upstream remote
git remote add upstream https://github.com/vitali87/code-graph-rag.git

# Verify
git remote -v
```

### "You have uncommitted changes"

```bash
# Either commit them
git commit -am "WIP: work in progress"

# Or stash them
git stash
./sync-upstream.sh sync
git stash pop
```

### "Merge conflict detected"

Follow the conflict resolution steps above. Don't panic!

### "Dev has diverged from origin"

```bash
# If you've been working locally without pushing
git checkout dev
git pull --rebase origin dev
git push origin dev
```

### "Lost track of what's local vs upstream"

```bash
# See your local features
git log --oneline main..dev

# See what's in main from upstream
git log --oneline dev..main
```

## Sync Script Reference

### Commands

```bash
# Status check (safe, read-only)
./sync-upstream.sh status

# Dry run (safe, read-only)
./sync-upstream.sh dry-run

# Full sync (writes to main and dev)
./sync-upstream.sh sync

# Only update main (skip dev merge)
./sync-upstream.sh update-main

# Only merge main to dev (skip main update)
./sync-upstream.sh merge-to-dev

# Help
./sync-upstream.sh help
```

### What Each Command Does

| Command | Fetches? | Updates main? | Merges to dev? | Pushes? |
|---------|----------|---------------|----------------|---------|
| `status` | Yes | No | No | No |
| `dry-run` | Yes | No | No | No |
| `sync` | Yes | Yes | Yes | Yes |
| `update-main` | Yes | Yes | No | Yes |
| `merge-to-dev` | No | No | Yes | Yes |

## Integration with manage-graph.sh

After syncing upstream, your dev branch may have new features. Test them:

```bash
# 1. Sync upstream
./sync-upstream.sh sync

# 2. Stop old services
./manage-graph.sh stop-docker

# 3. Restart with latest code
docker-compose down -v  # Clear old data
./manage-graph.sh start-docker

# 4. Re-index
./manage-graph.sh index /path/to/repo

# 5. Watch
./manage-graph.sh watch /path/to/repo
```

## When to Skip Sync

Skip syncing if:

- ❌ You have uncommitted changes you're not ready to commit
- ❌ You're in the middle of a complex feature
- ❌ You know upstream has breaking changes you're not ready for
- ❌ You're about to release and want stability

**Do sync** before:
- ✅ Starting a new feature
- ✅ Reporting a bug (check if it's already fixed upstream)
- ✅ Contributing back to upstream
- ✅ A major release

## Summary

**Goal**: Keep your `dev` branch up-to-date with upstream while preserving your local features.

**Strategy**: Merge upstream changes into dev regularly.

**Tools**:
- `./sync-upstream.sh` - Automated sync script
- `git merge` - Integration strategy
- `dev` branch - Your integration point

**Workflow**:
1. Develop in `feature/*` branches
2. Merge features to `dev`
3. Periodically sync upstream into `dev`
4. Keep shipping your product

**Remember**: Your local features are **always preserved**. Sync is additive, not destructive.

---

For more information:
- Branch strategy: `.github/FORK_STRUCTURE.md`
- Fork setup: `.github/SETUP_GUIDE.md`
- Operations: `docs/MONITORING_AND_SETUP.md`
