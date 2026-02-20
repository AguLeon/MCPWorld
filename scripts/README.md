# Scripts

The scripts/ folder contains utilities for batch task execution and metrics collection:

| File                                   | Description                                      |
|----------------------------------------|--------------------------------------------------|
| entrypoint.sh                          | Main entry point for OpenMCP setup & launch      |
| config.cfg                             | Shared configuration for batch runs              |
| run_tasks_range.sh                     | Generic script to run a range of tasks           |
| run_vscode_range.sh                   | Run a range of VSCode tasks                      |
| run_obsidian_range.sh                 | Run a range of Obsidian tasks                    |
| run_vscode_then_obsidian_range.sh     | Run both suites sequentially                     |
| run_multi_model_benchmark.sh          | Automated multi-model benchmarking          |
| monitor_gpu.py                        | GPU metrics monitoring                     |
| kill_all_benchmarks.sh                | Kill all running benchmark processes        |
| collect_metrics.py                    | Parse result JSON and aggregate to CSV           |



## Sample Scripts to run

### Starting the Environment (entrypoint.sh)

The main entry point for setting up and launching OpenMCP:

```bash
# Usage: ./scripts/entrypoint.sh [--rebuild] <infrastructure_tag>

# Start the environment with infrastructure tag
./scripts/entrypoint.sh H100x1

# Force rebuild Docker images before starting
./scripts/entrypoint.sh --rebuild H100x1
```

The entrypoint script will:
1. Start Docker containers (automatically detects GPU availability)
2. Prompt you to install applications into the container
3. Optionally run the benchmark suite

### Installing Applications in the Container

> **Important:** Applications must be installed as the **root** user inside the container. The framework assumes that applications are installed by root, not the agent user.

To manually install applications, enter the container as root:

```bash
# Enter the container as root
docker exec -it -u root <container-name> /bin/bash

# Once inside, run the installation scripts (no sudo needed - you're already root)
/workspace/MCPWorld/docker/apps_install_scripts/vscode.sh
/workspace/MCPWorld/docker/apps_install_scripts/obsidian.sh
```

> **Note:** The app installation scripts do not use `sudo` as they are designed to be run as root. Running them as a non-root user will fail.

Alternatively, the `entrypoint.sh` script will prompt you to install applications automatically during setup.

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
