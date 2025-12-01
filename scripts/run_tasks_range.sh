#!/usr/bin/env bash
set -euo pipefail

usage() {
    echo "Usage: $0 <suite> <start_task_number> <end_task_number> [log_root]" >&2
    echo "suite must be either 'vscode' or 'obsidian'" >&2
}

if [[ $# -lt 3 ]]; then
    usage
    exit 1
fi

SUITE=$1
START=$2
END=$3
CUSTOM_LOG_ROOT=${4:-}

if [[ "$SUITE" != "vscode" && "$SUITE" != "obsidian" ]]; then
    usage
    exit 1
fi

if ! [[ "$START" =~ ^[0-9]+$ && "$END" =~ ^[0-9]+$ ]]; then
    echo "Start and end must be positive integers." >&2
    exit 1
fi

if ((START < 1)); then
    echo "Start task must be >= 1." >&2
    exit 1
fi

if ((END < START)); then
    echo "End task must be >= start task." >&2
    exit 1
fi

SCRIPT_DIR=$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)
REPO_ROOT=$(cd -- "$SCRIPT_DIR/.." >/dev/null 2>&1 && pwd)
cd "$REPO_ROOT"

MODEL=${MODEL:-qwen3-vl:32b}
PROVIDER=${PROVIDER:-openai}
OPENAI_BASE_URL=${OPENAI_BASE_URL:-http://127.0.0.1:11434}
OPENAI_ENDPOINT=${OPENAI_ENDPOINT:-/v1/chat/completions}

case "$SUITE" in
    vscode)
        TASK_ROOT="PC-Canary/tests/tasks/vscode"
        DEFAULT_LOG_ROOT="logs_computer_use_eval/vscode_runs"
        ;;
    obsidian)
        TASK_ROOT="PC-Canary/tests/tasks/obsidian"
        DEFAULT_LOG_ROOT="logs_computer_use_eval/obsidian_runs"
        ;;
esac

if [[ -n "$CUSTOM_LOG_ROOT" ]]; then
    LOG_ROOT="$CUSTOM_LOG_ROOT"
else
    LOG_ROOT="$DEFAULT_LOG_ROOT"
fi

SUMMARY_FILE="$LOG_ROOT/${SUITE}_batch_summary.csv"
METRICS_FILE="$LOG_ROOT/${SUITE}_metrics.csv"

mkdir -p "$LOG_ROOT"
printf "task_id,status,reason,log_dir\n" >"$SUMMARY_FILE"
printf "task_id,status,reason,total_duration_seconds,llm_call_count,total_tool_calls,total_error_count,total_steps,completed_steps,log_dir\n" >"$METRICS_FILE"

mapfile -t TASK_DIRS < <(find "$TASK_ROOT" -maxdepth 1 -mindepth 1 -type d -name "task??_*" | sort)
TOTAL_TASKS=${#TASK_DIRS[@]}

if ((TOTAL_TASKS == 0)); then
    echo "No tasks found under $TASK_ROOT" >&2
    exit 1
fi

if ((END > TOTAL_TASKS)); then
    echo "Requested end task $END exceeds total available tasks ($TOTAL_TASKS)." >&2
    exit 1
fi

echo ">>> Running $SUITE tasks $START through $END (of $TOTAL_TASKS total)"

for idx in $(seq "$START" "$END"); do
    task_dir=${TASK_DIRS[$((idx - 1))]}
    task_name=$(basename "$task_dir")
    TASK_ID="$SUITE/$task_name"

    echo ">>> Running $TASK_ID"

    set +e
    printf "\n" | python3 computer-use-demo/run_pure_computer_use_with_eval.py \
        --provider "$PROVIDER" \
        --openai_api_key dummy \
        --openai_base_url "$OPENAI_BASE_URL" \
        --openai_endpoint "$OPENAI_ENDPOINT" \
        --model "$MODEL" \
        --task_id "$TASK_ID" \
        --log_dir "$LOG_ROOT" \
        --exec_mode mixed
    TASK_EXIT=$?
    set -e

    FALLBACK_STATUS="success"
    FALLBACK_REASON=""
    if ((TASK_EXIT != 0)); then
        FALLBACK_STATUS="error"
        FALLBACK_REASON="runner_exit_code_${TASK_EXIT}"
    fi

    latest_dir=$(find "$LOG_ROOT" -maxdepth 1 -mindepth 1 -type d -printf '%T@ %p\n' 2>/dev/null | sort -nr | head -n1 | cut -d' ' -f2-)

    if [[ -z "$latest_dir" ]]; then
        python3 scripts/collect_metrics.py \
            --task-id "$TASK_ID" \
            --log-dir "missing_log_dir" \
            --summary "$SUMMARY_FILE" \
            --metrics "$METRICS_FILE" \
            --fallback-status "$FALLBACK_STATUS" \
            --fallback-reason "${FALLBACK_REASON:-'no_logs'}"
        continue
    fi

    result_file=$(find "$latest_dir" -maxdepth 1 -type f -name "result_*.json" -print -quit)

    if [[ -n "$result_file" ]]; then
        python3 scripts/collect_metrics.py \
            --result "$result_file" \
            --task-id "$TASK_ID" \
            --log-dir "$latest_dir" \
            --summary "$SUMMARY_FILE" \
            --metrics "$METRICS_FILE" \
            --fallback-status "$FALLBACK_STATUS" \
            --fallback-reason "$FALLBACK_REASON"
    else
        python3 scripts/collect_metrics.py \
            --task-id "$TASK_ID" \
            --log-dir "$latest_dir" \
            --summary "$SUMMARY_FILE" \
            --metrics "$METRICS_FILE" \
            --fallback-status "$FALLBACK_STATUS" \
            --fallback-reason "${FALLBACK_REASON:-'result_missing'}"
    fi
done

echo "Batch complete. Summary saved to $SUMMARY_FILE"
