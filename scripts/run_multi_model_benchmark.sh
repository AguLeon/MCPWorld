#!/usr/bin/env bash
# Multi-Model Benchmark Automation
# Run from host machine to benchmark multiple Ollama models automatically
#
# Usage:
#   ./run_multi_model_benchmark.sh [vscode|obsidian|both] [infrastructure_tag]
#
# Examples:
#   ./run_multi_model_benchmark.sh vscode single_GPU    # Only VSCode with single_GPU tag
#   ./run_multi_model_benchmark.sh obsidian cpu         # Only Obsidian with cpu tag
#   ./run_multi_model_benchmark.sh both edge            # Both with edge tag
#   ./run_multi_model_benchmark.sh vscode               # VSCode with default tag
#   ./run_multi_model_benchmark.sh                      # Both with default tag
set -euo pipefail

# Configuration (must be before cleanup function)
OLLAMA_CONTAINER="ollama"
MCPWORLD_CONTAINER="mcpworld"

# Cleanup function to kill all running processes in container and on host
cleanup_on_exit() {
    echo ""
    echo "=========================================="
    echo "Cleaning up processes..."
    echo "=========================================="

    # Clean up container processes with graceful shutdown first
    echo "Sending SIGTERM for graceful shutdown..."
    docker exec "$MCPWORLD_CONTAINER" bash -c "pkill -15 -f 'python.*run_pure_computer_use|bash.*run_tasks_range' || true" 2>/dev/null || true

    # Wait briefly for graceful shutdown
    sleep 2

    # Force kill any remaining processes
    echo "Force killing remaining processes..."
    docker exec "$MCPWORLD_CONTAINER" bash -c "pkill -9 -f 'python.*run_pure_computer_use|bash.*run_tasks_range' || true" 2>/dev/null || true

    # Kill any docker exec processes on host (graceful first)
    pkill -15 -f 'docker exec.*mcpworld.*run_tasks_range' 2>/dev/null || true
    sleep 1
    pkill -9 -f 'docker exec.*mcpworld.*run_tasks_range' 2>/dev/null || true

    # Kill any background jobs started by this script
    jobs -p | xargs -r kill -15 2>/dev/null || true
    sleep 1
    jobs -p | xargs -r kill -9 2>/dev/null || true

    echo "Cleanup complete."
}

# Set up trap to cleanup on Ctrl+C, termination, or exit
trap cleanup_on_exit SIGINT SIGTERM EXIT

# Parse arguments
BENCHMARK_TYPE="${1:-both}"
INFRASTRUCTURE_TAG="${2:-default}"

case "$BENCHMARK_TYPE" in
vscode | obsidian | both) ;;
*)
    echo "ERROR: Invalid benchmark type '$BENCHMARK_TYPE'"
    echo "Usage: $0 [vscode|obsidian|both] [infrastructure_tag]"
    exit 1
    ;;
esac

# Task ranges for each app
VSCODE_START=1
VSCODE_END=25
OBSIDIAN_START=1
OBSIDIAN_END=12

# Define models to benchmark (edit this list as needed)
MODELS=(
    "qwen3-vl:8b-instruct"
    # "qwen3-vl:235b-a22b-instruct"
    # "qwen3-vl:235b"
    "qwen3-vl:32b"
    "qwen3-vl:32b-instruct"
    "qwen3-vl:2b-instruct"
    "ministral-3:8b-instruct-2512-fp16"
    "ministral-3:14b-instruct-2512-fp16"
    "devstral-small-2:24b"
    "seamon67/Gemma3:27b"
    "PetrosStav/gemma3-tools:4b"
    "PetrosStav/gemma3-tools:12b"
    "PetrosStav/gemma3-tools:27b"
    # "llama4:17b-scout-16e-instruct-q4_K_M"
    # "llama4:17b-scout-16e-instruct-q8_0"
)

# You can also read from a file:
# mapfile -t MODELS < models.txt

echo "=========================================="
echo "Multi-Model Benchmark Automation"
echo "=========================================="
echo "Benchmark type: $BENCHMARK_TYPE"
echo "Infrastructure tag: $INFRASTRUCTURE_TAG"
echo "Models to benchmark: ${MODELS[@]}"
echo "Estimated time: ~30 min per model"
echo "=========================================="
echo ""

# Function to check if ollama model exists in the system
model_exists() {
    local model=$1
    docker exec "$OLLAMA_CONTAINER" sh -c "ollama list | tail -n +2 | awk '{print \$1}' | grep -q '^${model}\$'" 2>/dev/null
}

# Function to clean Ollama models
clean_ollama() {
    echo "[$(date +%H:%M:%S)] Cleaning Ollama models..."
    # List all models and remove them
    docker exec "$OLLAMA_CONTAINER" sh -c 'ollama list | tail -n +2 | awk "{print \$1}" | xargs -r -n1 ollama rm' || true
    echo "[$(date +%H:%M:%S)] Ollama cleaned"
}

# Function to load a model
load_model() {
    local model=$1
    echo "[$(date +%H:%M:%S)] Loading model: $model"
    # Run the model (pulls if needed, then exits immediately)
    docker exec "$OLLAMA_CONTAINER" ollama run "$model" --keepalive 0 </dev/null || {
        echo "ERROR: Failed to load model $model"
        return 1
    }
    echo "[$(date +%H:%M:%S)] Model loaded: $model"
}

# GPU monitoring helpers (use CLEAN_MODEL and INFRA_SUFFIX from caller)
start_gpu_monitor() {
    local suite=$1
    local gpu_log_dir="logs_computer_use_eval/${suite}_runs/gpu_logs"
    mkdir -p "$gpu_log_dir"
    GPU_LOG="${gpu_log_dir}/gpu_metrics_${CLEAN_MODEL}${INFRA_SUFFIX}.csv"
    python3 scripts/monitor_gpu.py "$GPU_LOG" 0.25 &
    GPU_MONITOR_PID=$!
    echo "[$(date +%H:%M:%S)] Started GPU monitoring (PID: $GPU_MONITOR_PID) -> $GPU_LOG"
}

stop_gpu_monitor() {
    kill $GPU_MONITOR_PID 2>/dev/null || true
    wait $GPU_MONITOR_PID 2>/dev/null || true
    echo "[$(date +%H:%M:%S)] Stopped GPU monitoring -> $GPU_LOG"
}

# Helper to run a single suite inside the container
run_suite() {
    local model=$1
    local suite=$2
    local infra_tag=$3
    local start=$4
    local end=$5
    docker exec "$MCPWORLD_CONTAINER" bash -c "
            export PATH='/home/agent/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' &&
            export DISPLAY=:4 &&
            export MODEL='$model' &&
            export INFRASTRUCTURE_TAG='$infra_tag' &&
            cd /workspace &&
            ./scripts/run_tasks_range.sh $suite $start $end
        " || {
        echo "ERROR: $suite benchmark failed for model $model"
        return 1
    }
}

# Function to run benchmark
run_benchmark() {
    local model=$1
    local bench_type=$2
    local infra_tag=$3
    echo "[$(date +%H:%M:%S)] Starting benchmark for: $model (type: $bench_type, infrastructure: $infra_tag)"

    case "$bench_type" in
    vscode)
        start_gpu_monitor vscode
        run_suite "$model" vscode "$infra_tag" $VSCODE_START $VSCODE_END || { stop_gpu_monitor; return 1; }
        stop_gpu_monitor
        ;;
    obsidian)
        start_gpu_monitor obsidian
        run_suite "$model" obsidian "$infra_tag" $OBSIDIAN_START $OBSIDIAN_END || { stop_gpu_monitor; return 1; }
        stop_gpu_monitor
        ;;
    both)
        start_gpu_monitor vscode
        run_suite "$model" vscode "$infra_tag" $VSCODE_START $VSCODE_END || { stop_gpu_monitor; return 1; }
        stop_gpu_monitor
        echo "[$(date +%H:%M:%S)] VSCode completed, waiting 5s before Obsidian..."
        sleep 5
        start_gpu_monitor obsidian
        run_suite "$model" obsidian "$infra_tag" $OBSIDIAN_START $OBSIDIAN_END || { stop_gpu_monitor; return 1; }
        stop_gpu_monitor
        ;;
    esac

    echo "[$(date +%H:%M:%S)] Benchmark completed for: $model"
}

# Main loop
TOTAL_MODELS=${#MODELS[@]}
CURRENT=0

for model in "${MODELS[@]}"; do
    CURRENT=$((CURRENT + 1))

    echo ""
    echo "=========================================="
    echo "Processing model $CURRENT/$TOTAL_MODELS: $model"
    echo "=========================================="

    # Step 1: Always clean Ollama to ensure fresh state
    clean_ollama

    # Step 2: Load model
    load_model "$model" || continue

    # Step 3: Set up model name vars used by GPU monitor helpers
    CLEAN_MODEL=$(echo "$model" | tr ':/' '-_')
    INFRA_SUFFIX="${INFRASTRUCTURE_TAG:+_${INFRASTRUCTURE_TAG}}"

    # Step 4: Run benchmark (GPU monitoring is handled per-suite inside run_benchmark)
    run_benchmark "$model" "$BENCHMARK_TYPE" "$INFRASTRUCTURE_TAG" || continue

    # Step 6: Clean up container state
    docker exec "$MCPWORLD_CONTAINER" bash -c "pkill -f 'obsidian|python.*run_pure_computer_use' || true" 2>/dev/null || true
    sleep 2

    # Wipe VSCode user_data_dir to prevent SIGSEGV on next model's first task
    echo "[$(date +%H:%M:%S)] Wiping VSCode user_data_dir..."
    docker exec "$MCPWORLD_CONTAINER" bash -c "rm -rf /workspace/.mcpworld/vscode/vscode_user_data_dir" 2>/dev/null || true

    echo "[$(date +%H:%M:%S)] ✓ Completed: $model ($CURRENT/$TOTAL_MODELS)"
    echo ""
done

echo ""
echo "=========================================="
echo "All benchmarks completed!"
echo "=========================================="
