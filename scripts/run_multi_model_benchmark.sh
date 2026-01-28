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

# Parse arguments
BENCHMARK_TYPE="${1:-both}"
INFRASTRUCTURE_TAG="${2:-default}"

case "$BENCHMARK_TYPE" in
    vscode|obsidian|both)
        ;;
    *)
        echo "ERROR: Invalid benchmark type '$BENCHMARK_TYPE'"
        echo "Usage: $0 [vscode|obsidian|both] [infrastructure_tag]"
        exit 1
        ;;
esac

# Configuration
OLLAMA_CONTAINER="ollama"
MCPWORLD_CONTAINER="mcpworld"

# Task ranges for each app
VSCODE_START=1
VSCODE_END=25
OBSIDIAN_START=1
OBSIDIAN_END=2

# Define models to benchmark (edit this list as needed)
MODELS=(
    # "qwen3-vl:2b"
    "qwen3-vl:8b-instruct"
    "qwen3-vl:32b-instruct"
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

# Function to run benchmark
run_benchmark() {
    local model=$1
    local bench_type=$2
    local infra_tag=$3
    echo "[$(date +%H:%M:%S)] Starting benchmark for: $model (type: $bench_type, infrastructure: $infra_tag)"

    case "$bench_type" in
        vscode)
            docker exec -i "$MCPWORLD_CONTAINER" bash -c "
                export PATH='/home/agent/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' &&
                export DISPLAY=:4 &&
                export MODEL='$model' &&
                export INFRASTRUCTURE_TAG='$infra_tag' &&
                cd /workspace &&
                ./scripts/run_tasks_range.sh vscode $VSCODE_START $VSCODE_END
            " || {
                echo "ERROR: VSCode benchmark failed for model $model"
                return 1
            }
            ;;
        obsidian)
            docker exec -i "$MCPWORLD_CONTAINER" bash -c "
                export PATH='/home/agent/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' &&
                export DISPLAY=:4 &&
                export MODEL='$model' &&
                export INFRASTRUCTURE_TAG='$infra_tag' &&
                cd /workspace &&
                ./scripts/run_tasks_range.sh obsidian $OBSIDIAN_START $OBSIDIAN_END
            " || {
                echo "ERROR: Obsidian benchmark failed for model $model"
                return 1
            }
            ;;
        both)
            docker exec -i "$MCPWORLD_CONTAINER" bash -c "
                export PATH='/home/agent/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' &&
                export DISPLAY=:4 &&
                export MODEL='$model' &&
                export INFRASTRUCTURE_TAG='$infra_tag' &&
                cd /workspace &&
                ./scripts/run_tasks_range.sh vscode $VSCODE_START $VSCODE_END
            " || {
                echo "ERROR: VSCode benchmark failed for model $model"
                return 1
            }
            echo "[$(date +%H:%M:%S)] VSCode completed, waiting 5s before Obsidian..."
            sleep 5
            docker exec -i "$MCPWORLD_CONTAINER" bash -c "
                export PATH='/home/agent/miniconda3/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin' &&
                export DISPLAY=:4 &&
                export MODEL='$model' &&
                export INFRASTRUCTURE_TAG='$infra_tag' &&
                cd /workspace &&
                ./scripts/run_tasks_range.sh obsidian $OBSIDIAN_START $OBSIDIAN_END
            " || {
                echo "ERROR: Obsidian benchmark failed for model $model"
                return 1
            }
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

    # Step 1: Clean Ollama
    clean_ollama

    # Step 2: Load model
    load_model "$model" || continue

    # Step 3: Run benchmark
    run_benchmark "$model" "$BENCHMARK_TYPE" "$INFRASTRUCTURE_TAG" || continue

    echo "[$(date +%H:%M:%S)] ✓ Completed: $model ($CURRENT/$TOTAL_MODELS)"
    echo ""
done

echo ""
echo "=========================================="
echo "All benchmarks completed!"
echo "=========================================="
