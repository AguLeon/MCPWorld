#!/usr/bin/env bash
# Emergency cleanup script to kill all benchmark-related processes
# Run this if Ctrl+C doesn't properly clean up

echo "Killing all benchmark-related processes..."

# Kill processes inside container
docker exec mcpworld bash -c "pkill -9 -f 'python.*run_pure_computer_use|code-server|obsidian|bash.*run_tasks_range' || true" 2>/dev/null || true

# Kill all docker exec processes related to mcpworld
pkill -9 -f 'docker exec.*mcpworld' 2>/dev/null || true

# Kill the master benchmark script itself
pkill -9 -f 'run_multi_model_benchmark.sh' 2>/dev/null || true

echo "Cleanup complete. Verifying..."

# Check if any processes remain
REMAINING=$(pgrep -f 'run_pure_computer_use|run_tasks_range|run_multi_model' 2>/dev/null | wc -l)
if [ "$REMAINING" -eq 0 ]; then
    echo "✓ All processes cleaned up successfully"
else
    echo "⚠ Warning: $REMAINING processes still running:"
    pgrep -f 'run_pure_computer_use|run_tasks_range|run_multi_model' -a
fi
