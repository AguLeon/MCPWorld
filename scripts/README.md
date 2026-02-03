# Scripts

The scripts/ folder contains utilities for batch task execution and metrics collection:

| File                                   | Description                                      |
|----------------------------------------|--------------------------------------------------|
| config.cfg                             | Shared configuration for batch runs              |
| models.cfg                             | List of models to benchmark                 |
| run_tasks_range.sh                     | Generic script to run a range of tasks           |
| run_vscode_range.sh                   | Run a range of VSCode tasks                      |
| run_obsidian_range.sh                 | Run a range of Obsidian tasks                    |
| run_vscode_then_obsidian_range.sh     | Run both suites sequentially                     |
| run_multi_model_benchmark.sh          | Automated multi-model benchmarking          |
| monitor_gpu.py                        | GPU metrics monitoring                     |
| kill_all_benchmarks.sh                | Kill all running benchmark processes        |
| collect_metrics.py                    | Parse result JSON and aggregate to CSV           |



## Sample Scripts to run

### Multi-model benchmarking (in host machine)
Automatically benchmark multiple models across VSCode and/or Obsidian task suites:

```bash
# Usage: ./run_multi_model_benchmark.sh [vscode|obsidian|both] [infrastructure_tag]

# Run VSCode tasks for all models with "single_GPU" tag
./scripts/run_multi_model_benchmark.sh vscode H100

# Run Obsidian tasks with "cpu" tag
./scripts/run_multi_model_benchmark.sh obsidian cpu_32GB

# Default: both suites, default tag
./scripts/run_multi_model_benchmark.sh
```

Features:

- Automatic model loading/unloading via Ollama
- GPU monitoring per model run
- Clean state between model runs
- Graceful cleanup on Ctrl+C

### GPU Monitoring
Monitor GPU metrics during benchmark runs:

```bash
python3 scripts/monitor_gpu.py output.csv 0.25  # Sample every 0.25 seconds
```

Output includes: timestamp, GPU utilization, memory usage, temperature, power.

### Running Batch Tasks (inside the test-environment container)
```bash
# Run VSCode tasks 1 through 25
./scripts/run_vscode_range.sh 1 25

# Run Obsidian tasks 1 through 12
./scripts/run_obsidian_range.sh 1 12

# Generic runner for any suite
./scripts/run_tasks_range.sh vscode 1 25 /logs/output
./scripts/run_tasks_range.sh obsidian 1 12 /logs/output
```
