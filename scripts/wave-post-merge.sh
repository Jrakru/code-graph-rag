#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <wave_id>"
    exit 1
}

[ $# -lt 1 ] && usage

WAVE_ID=$1

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAGENTS_ROOT="${WAGENTS_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROJECT_ROOT="${WAGENTS_PROJECT_ROOT:-}"

if [ -z "$PROJECT_ROOT" ] && [ -n "${WAGENTS_STATE_DIR:-}" ]; then
    PROJECT_ROOT="$(cd "$(dirname "$WAGENTS_STATE_DIR")" && pwd)"
fi

if [ -z "$PROJECT_ROOT" ] && [ -n "${WAGENTS_WAVE_DIR:-}" ]; then
    wave_parent="$WAGENTS_WAVE_DIR"
    while [ -n "$wave_parent" ] && [ "$(basename "$wave_parent")" != ".wagents" ]; do
        wave_parent="$(dirname "$wave_parent")"
        if [ "$wave_parent" = "/" ]; then
            wave_parent=""
            break
        fi
    done
    if [ -n "$wave_parent" ]; then
        PROJECT_ROOT="$(cd "$(dirname "$wave_parent")" && pwd)"
    fi
fi

if [ -z "$PROJECT_ROOT" ]; then
    PROJECT_ROOT="$(git -C "$PWD" rev-parse --show-toplevel 2>/dev/null || true)"
fi

if [ -z "$PROJECT_ROOT" ]; then
    echo "ERROR: Unable to determine project root." >&2
    exit 1
fi

wagents_cli() {
    if command -v wagents >/dev/null 2>&1; then
        wagents "$@"
        return $?
    fi

    if command -v poetry >/dev/null 2>&1 && [ -f "$WAGENTS_ROOT/pyproject.toml" ]; then
        (cd "$WAGENTS_ROOT" && poetry run wagents "$@")
        return $?
    fi

    echo "ERROR: wagents CLI not found in PATH." >&2
    return 1
}

if [ -n "${WAGENTS_WAVE_DIR:-}" ]; then
    WAVE_DIR="$WAGENTS_WAVE_DIR"
else
    if [ -n "${WAGENTS_SET_ID:-}" ]; then
        WAVE_DIR="$PROJECT_ROOT/.wagents/sets/${WAGENTS_SET_ID}/waves/${WAVE_ID}"
    else
        WAVE_DIR="$PROJECT_ROOT/.wagents/waves/${WAVE_ID}"
    fi
fi
CONFIG_FILE=""
for candidate in "$WAVE_DIR/config.yaml" "$WAVE_DIR/config.yml" "$WAVE_DIR/config.json"; do
    if [ -f "$candidate" ]; then
        CONFIG_FILE="$candidate"
        break
    fi
done

if [ -z "$CONFIG_FILE" ]; then
    SET_CONFIG="$(find "$PROJECT_ROOT/.wagents/sets" -maxdepth 4 -type f \( -path "*/waves/${WAVE_ID}/config.yaml" -o -path "*/waves/${WAVE_ID}/config.yml" -o -path "*/waves/${WAVE_ID}/config.json" \) -print -quit 2>/dev/null || true)"
    if [ -n "$SET_CONFIG" ]; then
        CONFIG_FILE="$SET_CONFIG"
        WAVE_DIR="$(dirname "$CONFIG_FILE")"
    fi
fi

if [ -z "$CONFIG_FILE" ]; then
    echo "ERROR: Wave config not found for ${WAVE_ID}" >&2
    exit 1
fi

CONFIG_JSON=""
cleanup_config_json() {
    if [ -n "$CONFIG_JSON" ] && [ -f "$CONFIG_JSON" ]; then
        rm -f "$CONFIG_JSON"
    fi
}
trap cleanup_config_json EXIT

case "$CONFIG_FILE" in
    *.yaml|*.yml)
        CONFIG_JSON="$(mktemp)"
        if command -v yq >/dev/null 2>&1; then
            yq '.' "$CONFIG_FILE" > "$CONFIG_JSON"
        elif command -v python >/dev/null 2>&1; then
            python - "$CONFIG_FILE" "$CONFIG_JSON" <<'PY'
import json
import sys

try:
    import yaml
except Exception as exc:
    raise SystemExit("ERROR: PyYAML is required to read YAML configs.") from exc

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    data = yaml.safe_load(handle)

with open(sys.argv[2], "w", encoding="utf-8") as handle:
    json.dump(data, handle)
PY
        else
            echo "ERROR: yq or python with PyYAML is required to read YAML configs." >&2
            exit 1
        fi
        CONFIG_FILE="$CONFIG_JSON"
        ;;
esac

get_jq() {
    local query=$1
    jq -r "$query" "$CONFIG_FILE"
}

get_jq_bool() {
    local query=$1
    local default=$2
    jq -r "if $query == null then $default else $query end" "$CONFIG_FILE"
}

BASE_BRANCH="$(get_jq '.base_branch // "main"')"
STAGING_BRANCH="$(get_jq '.merge_strategy.staging_branch // ("staging/" + .wave_id)')"
MERGE_TO_BASE="$(get_jq_bool '.merge_strategy.merge_to_base' true)"
PUSH_BASE="$(get_jq_bool '.merge_strategy.push' false)"

SET_ID="${WAGENTS_SET_ID:-}"
if [ -z "$SET_ID" ]; then
    case "$WAVE_DIR" in
        */.wagents/sets/*/waves/*)
            set_dir="$(dirname "$(dirname "$WAVE_DIR")")"
            SET_ID="$(basename "$set_dir")"
            ;;
    esac
fi
if [ -n "$SET_ID" ]; then
    set_coord="$PROJECT_ROOT/.wagents/sets/$SET_ID/set-coordination.json"
    if [ -f "$set_coord" ]; then
        set_branch="$(jq -r '.set_branch // empty' "$set_coord")"
        if [ -n "$set_branch" ] && [ "$BASE_BRANCH" != "$set_branch" ]; then
            echo "ERROR: wave base_branch '$BASE_BRANCH' does not match set_branch '$set_branch'." >&2
            echo "Update the wave config base_branch before running post-merge." >&2
            exit 1
        fi
    fi
fi

FAILURE_MODE="$(get_jq '.merge_strategy.failure_policy.mode // "investigate"')"
MAX_ATTEMPTS="$(get_jq '.merge_strategy.failure_policy.max_attempts // 2')"
FIX_BRANCH="$(get_jq '.merge_strategy.failure_policy.fix_branch // ("fix/" + .wave_id + "/qc")')"
RERUN_VALIDATION="$(get_jq_bool '.merge_strategy.failure_policy.rerun_validation' true)"
EMIT_REPORT="$(get_jq_bool '.merge_strategy.failure_policy.emit_report' true)"

REMEDIATION_ENABLED="$(get_jq_bool '.merge_strategy.failure_policy.remediation_agent.enabled' true)"
REMEDIATION_WORKTREE="$(get_jq '.merge_strategy.failure_policy.remediation_agent.worktree_name // empty')"
if [ -z "$REMEDIATION_WORKTREE" ] || [ "$REMEDIATION_WORKTREE" = "null" ]; then
    REMEDIATION_WORKTREE="${WAVE_ID}-qc-fix"
fi

REMEDIATION_BRANCH="$(get_jq '.merge_strategy.failure_policy.remediation_agent.branch_name // empty')"
if [ -z "$REMEDIATION_BRANCH" ] || [ "$REMEDIATION_BRANCH" = "null" ]; then
    REMEDIATION_BRANCH="$FIX_BRANCH"
fi

REMEDIATION_CODEX_CONFIG="$(get_jq '.merge_strategy.failure_policy.remediation_agent.codex_config // empty')"
if [ -z "$REMEDIATION_CODEX_CONFIG" ] || [ "$REMEDIATION_CODEX_CONFIG" = "null" ]; then
    REMEDIATION_CODEX_CONFIG='{"use_mcp":true,"full_auto":true,"approval_policy":"never","sandbox_mode":"danger-full-access","additional_args":["-c","sandbox_workspace_write.network_access=true"]}'
fi

log() {
    echo "[$(date -u +"%Y-%m-%dT%H:%M:%SZ")] $*"
}

ensure_fix_worktree() {
    local worktree_path="$WAVE_DIR/worktrees/$REMEDIATION_WORKTREE"
    if [ -d "$worktree_path" ]; then
        return 0
    fi

    local base_ref="$BASE_BRANCH"
    if git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$STAGING_BRANCH"; then
        base_ref="$STAGING_BRANCH"
    fi

    if git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$REMEDIATION_BRANCH"; then
        git -C "$PROJECT_ROOT" worktree add "$worktree_path" "$REMEDIATION_BRANCH"
    else
        git -C "$PROJECT_ROOT" worktree add -b "$REMEDIATION_BRANCH" "$worktree_path" "$base_ref"
    fi
}

write_report() {
    local reason=$1
    local report_path="$WAVE_DIR/logs/qc-investigation.md"
    local coord_file="$WAVE_DIR/coordination.json"

    if [ "$EMIT_REPORT" != "true" ]; then
        return 0
    fi

    {
        echo "# QC Investigation Report"
        echo ""
        echo "Wave: $WAVE_ID"
        echo "Reason: $reason"
        echo "Time: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
        echo ""
        echo "Failed agents:"
        jq -r '.agents[] | select(.status == "failed") | .id' "$coord_file" 2>/dev/null || true
        echo ""
        echo "Agent worktrees:"
        jq -r '.agents[] | select(.status == "failed") | "\(.id) \(.worktree_name)"' "$coord_file" 2>/dev/null || true
        echo ""
        echo "git status:"
        git -C "$PROJECT_ROOT" status -sb
        echo ""
        echo "recent commits:"
        git -C "$PROJECT_ROOT" --no-pager log --oneline -10
    } > "$report_path"
}

run_remediation_agent() {
    local reason=$1
    local attempt=${2:-}
    if [ "$REMEDIATION_ENABLED" != "true" ]; then
        log "Remediation agent disabled; skipping."
        return 1
    fi

    command -v codex >/dev/null 2>&1 || { log "codex is required for remediation agent"; return 1; }

    ensure_fix_worktree

    local worktree_path="$WAVE_DIR/worktrees/$REMEDIATION_WORKTREE"
    local mission_suffix="$reason"
    if [ -n "$attempt" ]; then
        mission_suffix="${mission_suffix}-${attempt}"
    fi
    local safe_suffix
    safe_suffix=$(echo "$mission_suffix" | tr ' /' '__')
    local mission_file="$WAVE_DIR/logs/remediation-mission-${safe_suffix}.md"
    local report_path="$WAVE_DIR/logs/qc-investigation.md"

    cat > "$mission_file" <<EOF
# Mission: QC Remediation Agent

## Goal
Investigate the failure reason: ${reason}.
Fix issues so that validation + QC pass.

## Context
- Wave: ${WAVE_ID}
- Project root: ${PROJECT_ROOT}
- Report: ${report_path}
- Fix branch: ${REMEDIATION_BRANCH}

## Instructions
1. Open the report and review the failing agents or QC errors.
2. Fix the issues in this worktree and commit to ${REMEDIATION_BRANCH}.
3. If failures relate to a specific agent branch, you may patch that branch instead.
4. Keep commits small and focused.
EOF

    local use_mcp
    use_mcp=$(echo "$REMEDIATION_CODEX_CONFIG" | jq -r 'if .use_mcp == null then true else .use_mcp end' 2>/dev/null || echo "true")
    local full_auto
    full_auto=$(echo "$REMEDIATION_CODEX_CONFIG" | jq -r 'if .full_auto == null then true else .full_auto end' 2>/dev/null || echo "true")
    local profile
    profile=$(echo "$REMEDIATION_CODEX_CONFIG" | jq -r '.profile // empty' 2>/dev/null || echo "")

    local model
    model=$(echo "$REMEDIATION_CODEX_CONFIG" | jq -r '.model // empty' 2>/dev/null || echo "")

    local reasoning_effort
    reasoning_effort=$(echo "$REMEDIATION_CODEX_CONFIG" | jq -r '.reasoning_effort // empty' 2>/dev/null || echo "")

    local approval_policy
    approval_policy=$(echo "$REMEDIATION_CODEX_CONFIG" | jq -r '.approval_policy // empty' 2>/dev/null || echo "")

    local sandbox_mode
    sandbox_mode=$(echo "$REMEDIATION_CODEX_CONFIG" | jq -r '.sandbox_mode // empty' 2>/dev/null || echo "")

    local -a additional_args=()
    if echo "$REMEDIATION_CODEX_CONFIG" | jq -e '.additional_args? | type == "array"' >/dev/null 2>&1; then
        mapfile -t additional_args < <(echo "$REMEDIATION_CODEX_CONFIG" | jq -r '.additional_args[]')
    fi

    if [ ${#additional_args[@]} -gt 0 ]; then
        local -a filtered_args=()
        local idx=0
        while [ $idx -lt ${#additional_args[@]} ]; do
            local arg="${additional_args[$idx]}"
            if [ "$arg" = "-c" ]; then
                local next=$((idx + 1))
                if [ $next -lt ${#additional_args[@]} ] && [[ "${additional_args[$next]}" == sandbox_workspace_write.writable_roots=* ]]; then
                    idx=$((idx + 2))
                    continue
                fi
            fi
            filtered_args+=("$arg")
            idx=$((idx + 1))
        done
        additional_args=("${filtered_args[@]}")
    fi

    local has_network_access_arg="false"
    for arg in "${additional_args[@]}"; do
        if [[ "$arg" == *sandbox_workspace_write.network_access* ]]; then
            has_network_access_arg="true"
            break
        fi
    done
    if [ "$has_network_access_arg" != "true" ]; then
        additional_args+=("-c" "sandbox_workspace_write.network_access=true")
    fi

    if [ -z "$sandbox_mode" ] || [ "$sandbox_mode" = "workspace-write" ] || [ "$sandbox_mode" = "workspace_write" ]; then
        local state_dir="$PROJECT_ROOT/.wagents"
        local -a roots=("$worktree_path" "$WAVE_DIR" "$state_dir")

        local git_dir=""
        git_dir=$(git -C "$worktree_path" rev-parse --git-dir 2>/dev/null || true)
        if [ -n "$git_dir" ]; then
            if [[ "$git_dir" != /* ]]; then
                git_dir="$worktree_path/$git_dir"
            fi
            roots+=("$git_dir")
        fi

        local common_dir=""
        common_dir=$(git -C "$worktree_path" rev-parse --git-common-dir 2>/dev/null || true)
        if [ -n "$common_dir" ]; then
            if [[ "$common_dir" != /* ]]; then
                common_dir="$worktree_path/$common_dir"
            fi
            roots+=("$common_dir")
        fi

        local -a unique_roots=()
        local root
        for root in "${roots[@]}"; do
            [ -z "$root" ] && continue
            local seen=false
            for existing in "${unique_roots[@]}"; do
                if [ "$existing" = "$root" ]; then
                    seen=true
                    break
                fi
            done
            if [ "$seen" = "false" ]; then
                unique_roots+=("$root")
            fi
        done

        for root in "${unique_roots[@]}"; do
            local existing_idx=""
            local idx=0
            while [ $idx -lt ${#additional_args[@]} ]; do
                if [ "${additional_args[$idx]}" = "--add-dir" ]; then
                    local next=$((idx + 1))
                    if [ $next -lt ${#additional_args[@]} ] && [ "${additional_args[$next]}" = "$root" ]; then
                        existing_idx=$idx
                        break
                    fi
                fi
                idx=$((idx + 1))
            done
            if [ -z "$existing_idx" ]; then
                additional_args+=("--add-dir" "$root")
            fi
        done
    fi

    if [ "$use_mcp" = "true" ]; then
        command -v tmux >/dev/null 2>&1 || { log "tmux is required for MCP remediation agent"; return 1; }

        local session_name="${WAVE_ID}-remediation-${safe_suffix}"
        local done_file="$WAVE_DIR/logs/remediation-done-${safe_suffix}.flag"
        local exit_file="$WAVE_DIR/logs/remediation-exit-${safe_suffix}.txt"
        rm -f "$done_file" "$exit_file"

        if tmux has-session -t "$session_name" 2>/dev/null; then
            log "Existing remediation tmux session found; replacing: $session_name"
            tmux kill-session -t "$session_name"
        fi

        tmux new-session -d -s "$session_name" -c "$worktree_path" -n "agent"
        tmux send-keys -t "$session_name:agent" "clear" C-m
        tmux send-keys -t "$session_name:agent" "echo '=== Remediation Agent: $WAVE_ID ==='" C-m
        tmux send-keys -t "$session_name:agent" "echo 'Mission: $mission_file'" C-m
        tmux send-keys -t "$session_name:agent" "echo ''" C-m

        local eff_profile="${profile:-autonomous-agent}"
        local codex_args=(codex --search -p "$eff_profile")
        if [ "$full_auto" = "true" ]; then
            codex_args+=(--full-auto)
        fi
        if [ -n "$model" ]; then
            codex_args+=(--model "$model")
        fi
        if [ -n "$reasoning_effort" ]; then
            codex_args+=(-c "model_reasoning_effort=\"$reasoning_effort\"")
        fi
        if [ ${#additional_args[@]} -gt 0 ]; then
            codex_args+=("${additional_args[@]}")
        fi
        if [ -n "$approval_policy" ]; then
            codex_args+=(-c "approval_policy=\"$approval_policy\"")
        fi
        if [ -n "$sandbox_mode" ]; then
            codex_args+=(-c "sandbox_mode=\"$sandbox_mode\"")
        fi

        local codex_cmd_str=""
        printf -v codex_cmd_str '%q ' "${codex_args[@]}"
        codex_cmd_str="${codex_cmd_str% }"
        tmux send-keys -t "$session_name:agent" "$codex_cmd_str \"\$(cat \"$mission_file\")\"; echo \\$? > \"$exit_file\"; touch \"$done_file\"" C-m

        log "Starting remediation agent in tmux session: $session_name"
        log "Attach with: tmux attach -t $session_name"

        while [ ! -f "$done_file" ]; do
            sleep 5
        done

        if [ -f "$exit_file" ]; then
            log "Remediation agent exit code: $(cat "$exit_file")"
        fi
        return 0
    fi

    local codex_args=(codex exec --cd "$worktree_path" --skip-git-repo-check --json --output-last-message "$WAVE_DIR/logs/remediation-last-message.txt")
    if [ "$full_auto" = "true" ]; then
        codex_args+=(--full-auto)
    fi
    if [ -n "$profile" ]; then
        codex_args+=(-p "$profile")
    fi
    if [ -n "$model" ]; then
        codex_args+=(--model "$model")
    fi
    if [ -n "$reasoning_effort" ]; then
        codex_args+=(-c "model_reasoning_effort=\"$reasoning_effort\"")
    fi
    if [ ${#additional_args[@]} -gt 0 ]; then
        codex_args+=("${additional_args[@]}")
    fi
    if [ -n "$approval_policy" ]; then
        codex_args+=(-c "approval_policy=\"$approval_policy\"")
    fi
    if [ -n "$sandbox_mode" ]; then
        codex_args+=(-c "sandbox_mode=\"$sandbox_mode\"")
    fi

    log "Starting remediation agent in $worktree_path"
    "${codex_args[@]}" < "$mission_file" \
        > "$WAVE_DIR/logs/remediation-output.jsonl" \
        2> "$WAVE_DIR/logs/remediation-stderr.log"
}

merge_fix_branch_into_staging() {
    if ! git -C "$PROJECT_ROOT" show-ref --verify --quiet "refs/heads/$REMEDIATION_BRANCH"; then
        return 0
    fi

    local ahead
    ahead=$(git -C "$PROJECT_ROOT" rev-list --count "$STAGING_BRANCH..$REMEDIATION_BRANCH" 2>/dev/null || echo "0")
    if [ "$ahead" -gt 0 ]; then
        log "Merging remediation branch into staging..."
        git -C "$PROJECT_ROOT" checkout "$STAGING_BRANCH"
        git -C "$PROJECT_ROOT" merge --no-ff "$REMEDIATION_BRANCH" -m "Merge remediation fixes for $WAVE_ID"
    fi
}

run_qc_commands() {
    local qc_failed=false
    mapfile -t qc_commands < <(jq -r '.merge_strategy.qc_commands[]? // empty' "$CONFIG_FILE")

    if [ ${#qc_commands[@]} -eq 0 ]; then
        log "No QC commands configured."
        return 0
    fi

    for cmd in "${qc_commands[@]}"; do
        [ -z "$cmd" ] && continue
        log "QC: $cmd"
        if ! (cd "$PROJECT_ROOT" && eval "$cmd"); then
            log "QC failed: $cmd"
            qc_failed=true
            break
        fi
    done

    if [ "$qc_failed" = "true" ]; then
        return 1
    fi
}

attempt=1
while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
    log "Post-merge attempt $attempt/$MAX_ATTEMPTS"
    failure_reason=""

    if wagents_cli --project-root "$PROJECT_ROOT" validate-completion "$WAVE_ID"; then
        log "Validation passed."
        wagents_cli --project-root "$PROJECT_ROOT" merge "$WAVE_ID" --target "$STAGING_BRANCH" --require-validated --no-pull
        git -C "$PROJECT_ROOT" checkout "$STAGING_BRANCH"
        merge_fix_branch_into_staging

        if run_qc_commands; then
            log "QC passed."
            if [ "$MERGE_TO_BASE" = "true" ]; then
                git -C "$PROJECT_ROOT" checkout "$BASE_BRANCH"
                git -C "$PROJECT_ROOT" merge --no-ff "$STAGING_BRANCH" -m "Merge staging for $WAVE_ID"
            fi
            if [ "$PUSH_BASE" = "true" ]; then
                git -C "$PROJECT_ROOT" push origin "$BASE_BRANCH"
            fi
            log "Post-merge flow completed."
            exit 0
        else
            failure_reason="qc_failed"
            write_report "$failure_reason"
        fi
    else
        failure_reason="validation_failed"
        write_report "$failure_reason"
    fi

    if [ "$FAILURE_MODE" != "investigate" ]; then
        log "Failure mode is $FAILURE_MODE; stopping."
        exit 1
    fi

    if [ -z "$failure_reason" ]; then
        failure_reason="attempt-${attempt}"
    fi
    run_remediation_agent "$failure_reason" "$attempt" || true

    if [ "$RERUN_VALIDATION" = "true" ]; then
        wagents_cli --project-root "$PROJECT_ROOT" validate-completion "$WAVE_ID" || true
    fi

    attempt=$((attempt + 1))
done

log "Exhausted remediation attempts."
exit 1
