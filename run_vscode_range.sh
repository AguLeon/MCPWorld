#!/usr/bin/env bash
set -euo pipefail

START=${1:-1}
END=${2:-25}
MODEL=${MODEL:-qwen3-vl:32b}
PROVIDER=${PROVIDER:-openai}
OPENAI_BASE_URL=${OPENAI_BASE_URL:-http://host.docker.internal:11434}
OPENAI_ENDPOINT=${OPENAI_ENDPOINT:-/v1/chat/completions}
LOG_ROOT=${LOG_ROOT:-logs_computer_use_eval}
SUMMARY=${SUMMARY:-logs_computer_use_eval/vscode_batch_summary.csv}

THIS_DIR=$(cd -- "$(dirname "$0")" >/dev/null 2>&1 && pwd)
cd "$THIS_DIR"

mkdir -p "$(dirname "$SUMMARY")"
if [ ! -f "$SUMMARY" ]; then
  echo "task_id,status,log_dir" > "$SUMMARY"
fi

mapfile -t task_dirs < <(ls -1 PC-Canary/tests/tasks/vscode/task??_* | sort)
for idx in $(seq "$START" "$END"); do
  task_dir=${task_dirs[$((idx-1))]}
  task_name=$(basename "$task_dir")
  TASK_ID="vscode/$task_name"
  echo ">>> Running $TASK_ID"
  printf "\n" | python3 computer-use-demo/run_pure_computer_use_with_eval.py \
    --provider "$PROVIDER" \
    --openai_api_key dummy \
    --openai_base_url "$OPENAI_BASE_URL" \
    --openai_endpoint "$OPENAI_ENDPOINT" \
    --model "$MODEL" \
    --task_id "$TASK_ID" \
    --log_dir "$LOG_ROOT" \
    --exec_mode mixed
  RUN_DIR=$(ls -dt "$LOG_ROOT"/* | head -n1)
  RESULT_FILE=$(find "$RUN_DIR" -name "result_*.json" -print -quit)
  STATUS=$(jq -r '.status // "unknown"' "$RESULT_FILE" 2>/dev/null || echo "unknown")
  echo "$TASK_ID,$STATUS,$RUN_DIR" >> "$SUMMARY"
done

echo "Batch complete. Summary at $SUMMARY"
