#!/usr/bin/env bash
set -euo pipefail

./scripts/run_tasks_range.sh vscode 1 25
sleep 5
./scripts/run_tasks_range.sh obsidian 1 12
