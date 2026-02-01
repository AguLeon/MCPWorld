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

CONFIG_FILE="/workspace/scripts/config.cfg"

# Preserve ONLY MODEL and INFRASTRUCTURE_TAG if already set (from parent script)
# CRITICAL: All other parameters (PROVIDER, OPENAI_BASE_URL, EXEC_MODE, etc.)
# MUST come from config.cfg and should NOT be overridden
SAVED_MODEL="${MODEL:-}"
SAVED_INFRA_TAG="${INFRASTRUCTURE_TAG:-}"

# Source config.cfg - loads all critical parameters
# PROVIDER, OPENAI_BASE_URL, OPENAI_ENDPOINT, EXEC_MODE, timeouts always use config.cfg values
source "$CONFIG_FILE"

# Restore ONLY MODEL and INFRASTRUCTURE_TAG if set by parent script
# This allows run_multi_model_benchmark.sh to override the model being tested
if [[ -n "$SAVED_MODEL" ]]; then
    MODEL="$SAVED_MODEL"
fi
if [[ -n "$SAVED_INFRA_TAG" ]]; then
    INFRASTRUCTURE_TAG="$SAVED_INFRA_TAG"
fi

# Export variables for Python code to access via os.environ
export MODEL                # May be overridden by parent script
export PROVIDER             # Always from config.cfg
export OPENAI_BASE_URL      # Always from config.cfg
export OPENAI_ENDPOINT      # Always from config.cfg
export INFRASTRUCTURE_TAG   # May be overridden by parent script
export MAX_LLM_CALLS        # Always from config.cfg

TASK_TIMEOUT=${TASK_TIMEOUT:-600}
TOTAL_TIMEOUT=${TOTAL_TIMEOUT:-$TASK_TIMEOUT}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY:-"dummy"}

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

# Generate run-level timestamp (once per batch)
RUN_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Clean model name (replace : with -)
CLEAN_MODEL_NAME=$(echo "$MODEL" | tr ':/' '-_')

# Create intermediate run folder with model name and infrastructure tag
INFRASTRUCTURE_SUFFIX="${INFRASTRUCTURE_TAG:+_${INFRASTRUCTURE_TAG}}"
RUN_FOLDER="${LOG_ROOT}/${CLEAN_MODEL_NAME}${INFRASTRUCTURE_SUFFIX}_run_${RUN_TIMESTAMP}"
mkdir -p "$RUN_FOLDER"

printf "task_id,status,reason,log_dir\n" >"$SUMMARY_FILE"
printf "task_id,status,reason,total_duration_seconds,llm_call_count,total_tool_calls,total_error_count,total_steps,completed_steps,avg_gpu_util_pct,max_gpu_util_pct,avg_vram_mb,peak_vram_mb,avg_temp_c,max_temp_c,avg_power_w,max_power_w,total_energy_joules,total_energy_kwh,avg_tokens_per_second,overall_tokens_per_second,total_completion_tokens,total_generation_time_sec,log_dir\n" >"$METRICS_FILE"

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
    # Create task folder inside the run folder
    TASK_FOLDER="${RUN_FOLDER}/${task_name}_${CLEAN_MODEL_NAME}${INFRASTRUCTURE_SUFFIX}"
    mkdir -p "$TASK_FOLDER"
    RUN_LOG_DIR="$TASK_FOLDER"

    echo ">>> Running $TASK_ID"

    # Ensure VSCode is fully stopped from previous task
    # Check for any lingering code-oss processes
    if pgrep -f "code-oss.*vscode_user_data_dir" >/dev/null 2>&1; then
        echo "[WARN] VSCode processes still running from previous task, cleaning up..."

        # Try SIGTERM first (graceful)
        pkill -15 -f "code-oss.*vscode_user_data_dir" 2>/dev/null || true

        # Wait up to 10 seconds for processes to exit
        for i in {1..10}; do
            if ! pgrep -f "code-oss.*vscode_user_data_dir" >/dev/null 2>&1; then
                echo "[INFO] VSCode processes exited after ${i} seconds"
                break
            fi
            sleep 1
        done

        # If still running, force kill
        if pgrep -f "code-oss.*vscode_user_data_dir" >/dev/null 2>&1; then
            echo "[WARN] VSCode processes still running after 10s, force killing..."
            pkill -9 -f "code-oss.*vscode_user_data_dir" 2>/dev/null || true
            sleep 2
        fi
    fi

    # Also ensure port 5000 is free
    if command -v fuser >/dev/null 2>&1 && fuser 5000/tcp >/dev/null 2>&1; then
        echo "[WARN] Port 5000 still in use, cleaning up..."
        fuser -k -TERM 5000/tcp >/dev/null 2>&1 || true
        sleep 2
        # Force kill if still in use
        fuser -k -KILL 5000/tcp >/dev/null 2>&1 || true
        sleep 1
    fi

    # Extra safety: wait a moment for file system to settle
    sleep 1

    set +e
    timeout --preserve-status "$TOTAL_TIMEOUT" python3 computer-use-demo/run_pure_computer_use_with_eval.py \
        --provider "$PROVIDER" \
        --openai_api_key dummy \
        --openai_base_url "$OPENAI_BASE_URL" \
        --openai_endpoint "$OPENAI_ENDPOINT" \
        --model "$MODEL" \
        --task_id "$TASK_ID" \
        --log_dir "$RUN_LOG_DIR" \
        --exec_mode "$EXEC_MODE" \
        --timeout "$TASK_TIMEOUT" \
        --api_key "$ANTHROPIC_API_KEY" \
        --auto-accept-default
    TASK_EXIT=$?
    set -e

    FALLBACK_STATUS="success"
    FALLBACK_REASON=""
    if ((TASK_EXIT == 124)); then
        FALLBACK_STATUS="error"
        FALLBACK_REASON="timeout_${TOTAL_TIMEOUT}s"
    elif ((TASK_EXIT != 0)); then
        FALLBACK_STATUS="error"
        FALLBACK_REASON="runner_exit_code_${TASK_EXIT}"
    fi

    if [[ ! -d "$RUN_LOG_DIR" ]]; then
        python3 scripts/collect_metrics.py \
            --task-id "$TASK_ID" \
            --log-dir "missing_log_dir" \
            --summary "$SUMMARY_FILE" \
            --metrics "$METRICS_FILE" \
            --fallback-status "$FALLBACK_STATUS" \
            --fallback-reason "${FALLBACK_REASON:-'no_logs'}"
        continue
    fi

    result_file=$(find "$RUN_LOG_DIR" -type f -name "result_*.json" -print -quit)

    if [[ -n "$result_file" ]]; then
        python3 scripts/collect_metrics.py \
            --result "$result_file" \
            --task-id "$TASK_ID" \
            --log-dir "$RUN_LOG_DIR" \
            --summary "$SUMMARY_FILE" \
            --metrics "$METRICS_FILE" \
            --fallback-status "$FALLBACK_STATUS" \
            --fallback-reason "$FALLBACK_REASON"
    else
        python3 scripts/collect_metrics.py \
            --task-id "$TASK_ID" \
            --log-dir "$RUN_LOG_DIR" \
            --summary "$SUMMARY_FILE" \
            --metrics "$METRICS_FILE" \
            --fallback-status "$FALLBACK_STATUS" \
            --fallback-reason "${FALLBACK_REASON:-'result_missing'}"
    fi
done

echo "Batch complete. Summary saved to $SUMMARY_FILE"
