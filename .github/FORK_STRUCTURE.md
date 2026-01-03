# Fork Structure and Branch Management

This document describes the branch structure and workflow for managing contributions to code-graph-rag.

## Overview

We maintain a structured fork of [vitali87/code-graph-rag](https://github.com/vitali87/code-graph-rag) with the following branches:

```
upstream/main
    ↓ (fetch & sync)
origin/main (mirror of upstream)
    ↓ (branch off)
origin/dev (local development)
    ↓ (feature branches)
origin/feature/* (individual features)
```

## Branch Purposes

### `main` (Production - Synced with Upstream)

- **Purpose**: Mirror of upstream repository
- **Who pushes to it**: Automation only (via fetch from upstream)
- **Rules**:
  - Always matches `upstream/main`
  - Never commit directly to this branch
  - Used to create PRs against upstream
  - Safe to deploy if using upstream releases

**Usage**:
```bash
# Keep it in sync with upstream
git fetch upstream
git checkout main
git pull upstream main
git push origin main
```

### `dev` (Local Development Base)

- **Purpose**: Base branch for all local features and improvements
- **Who pushes to it**: You (for merging feature branches)
- **Rules**:
  - Branches off from `main` (stays synced)
  - Accumulates local features not yet in upstream
  - Should stay ahead of `main` (contains local improvements)
  - Mergeable and testable state maintained

**Usage**:
```bash
# Keep dev synced with latest main
git checkout dev
git pull origin dev
git merge main  # If main was updated from upstream

# Create feature branch from dev
git checkout -b feature/your-feature dev
```

### `feature/*` (Feature Branches)

- **Purpose**: Individual feature development
- **Who pushes to it**: You
- **Naming**: `feature/descriptive-name` or `fix/bug-name`
- **Rules**:
  - Branch from `dev`
  - Focused on single feature/fix
  - Create PR to `dev` (not directly to `main`)
  - Delete after merge

**Workflow**:
```bash
# Create feature branch
git checkout -b feature/my-feature dev
git push origin feature/my-feature

# Make commits
git commit -am "implement feature"
git push origin feature/my-feature

# Create PR on GitHub: feature/my-feature → dev
# After review, merge into dev
# Delete feature branch
git push origin --delete feature/my-feature
git branch -d feature/my-feature
```

## Typical Workflows

### Sync with Upstream

When upstream has new changes you want:

```bash
# Update local upstream tracking
git fetch upstream

# Update main to match upstream
git checkout main
git pull upstream main
git push origin main

# Rebase dev on top of new main
git checkout dev
git rebase main
git push origin dev
```

### Create a Feature

For a new local feature/fix:

```bash
# Start from latest dev
git fetch origin
git checkout -b feature/my-feature origin/dev

# Develop and commit
git commit -am "add my feature"
git push origin feature/my-feature

# Create PR on GitHub: feature/my-feature → dev
```

### Contribute Upstream

When your feature is ready to send upstream:

```bash
# Ensure it's clean and well-tested
git checkout feature/my-feature
git log origin/main..HEAD  # See commits to send

# Option 1: Create PR directly from GitHub UI
#   PRs → New → base: vitali87/main, compare: feature/my-feature

# Option 2: Cherry-pick to main and create traditional PR
git checkout main
git pull upstream main
git checkout -b feature/upstream-contribution main
git cherry-pick feature/my-feature...
git push origin feature/upstream-contribution
# Create PR on GitHub
```

## Remote Configuration

After cloning, configure remotes:

```bash
git remote -v
# origin    https://github.com/Jrakru/code-graph-rag.git (your fork)
# upstream  https://github.com/vitali87/code-graph-rag.git (original)

# If not present, add upstream:
git remote add upstream https://github.com/vitali87/code-graph-rag.git
```

Configure Git to automatically fetch upstream:

```bash
# Add to .git/config or run:
git config branch.main.remote upstream
git config branch.main.merge refs/heads/main
```

## Branch Responsibilities

| Branch | Tracks | Role | Deploy Safe |
|--------|--------|------|-----------|
| `main` | `upstream/main` | Upstream mirror | ✅ Yes |
| `dev` | `main` + local features | Development base | ⚠️ Usually |
| `feature/*` | `dev` | Active feature | ❌ No |

## Merging Strategy

### Into `dev`

1. Create feature branch from `dev`
2. Develop and test thoroughly
3. Create PR: `feature/X` → `dev`
4. Require code review
5. Squash & merge (to keep history clean)
6. Delete feature branch

### Into `main`

Only in these cases:
- Merging upstream changes: `git pull upstream main`
- About to create upstream PR: cherry-pick from `dev`

**Never** commit directly to `main`.

## Handling Conflicts

### Feature conflicts with dev

```bash
git checkout feature/my-feature
git fetch origin
git merge origin/dev

# Resolve conflicts
git add .
git commit -m "resolve conflicts with dev"
git push origin feature/my-feature
```

### Dev conflicts with main (upstream changes)

```bash
git checkout dev
git fetch upstream
git merge upstream/main

# Or rebase for cleaner history:
git rebase upstream/main

# Resolve conflicts and continue
git rebase --continue
```

## GitHub Configuration

### Branch Protection Rules

Set up on GitHub for `main`:
- ✅ Require PR reviews (1+)
- ✅ Require status checks to pass
- ✅ Require branches up to date
- ✅ Restrict who can push (admins only)
- ❌ Allow force pushes

Set up on GitHub for `dev`:
- ✅ Require PR reviews (1+)
- ✅ Require status checks to pass
- ❌ Restrict who can push (allow developers)
- ❌ Allow force pushes (optional)

### Default Branch

- Set `dev` as the default branch for development work
- Keep `main` as secondary (upstream mirror)

## Common Tasks

### "I want to update my dev with latest upstream"

```bash
git fetch upstream
git checkout main
git pull upstream main
git push origin main
git checkout dev
git merge main
git push origin dev
```

### "My feature is ready to send to upstream"

```bash
# Ensure it's on main-based branch
git checkout -b feature/upstream-ready main
git cherry-pick feature/my-feature...
git push origin feature/upstream-ready

# Create PR on GitHub (to vitali87/main)
```

### "I want to test if my feature works before PRing"

```bash
# Push feature branch
git push origin feature/my-feature

# On GitHub, create PR to `dev` and merge
# Or test locally:
git checkout dev
git merge feature/my-feature
# test...
git reset --hard origin/dev  # undo merge
```

### "I merged a feature and now dev is broken"

```bash
# Revert the merge
git log dev --oneline  # find merge commit
git revert -m 1 <merge-commit-hash>
git push origin dev

# Or just remove the feature branch
git checkout dev
git reset --hard origin/dev
git merge origin/feature/working-feature
```

## Tips & Best Practices

1. **Keep `main` clean** - It should always match upstream
2. **Use `dev` as your safe base** - Merge features into dev for testing
3. **Short-lived feature branches** - Delete after merge
4. **Descriptive branch names** - `feature/debounce-watcher`, not `feature/123`
5. **Atomic commits** - One logical change per commit
6. **Sync often** - Pull upstream changes frequently to avoid conflicts
7. **Test before merging** - Always verify features work in dev
8. **Document your features** - Add to README or docs/

## References

- [GitHub Fork Flow](https://gist.github.com/Chaser324/ce0505343f45739e1e50)
- [Git Workflow Comparison](https://www.atlassian.com/git/tutorials/comparing-workflows)
- Original repo: https://github.com/vitali87/code-graph-rag