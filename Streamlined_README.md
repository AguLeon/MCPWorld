# Streamlined Startup Guide

Kick off the MCPWorld environment with the essentials below. Each step explains what the command accomplishes so the system can be run with confidence.

## 1. Start the Docker Workspace

Bring up the container stack defined in `docker-compose.yml`. This boots the desktop environment, VNC/noVNC services, Ollama, and prepares the shared workspace volume.

```bash
cd ~/MCPWorld/docker
docker compose up -d
```

### Optional: install extra apps while the container starts

Toggle installers by passing a comma-separated list via `INSTALL_APPS`. Examples:

```bash
INSTALL_APPS=freetube,vscode docker compose up -d
```

```bash
INSTALL_APPS=freetube docker compose up
```

```bash
# No additional installers (default)
docker compose up
```

- Supported values today: `freetube`, `vscode` (more are coming).
- Installers run during container startup; logs land in `/tmp/freetube_install.log` or `/tmp/vscode_install.log` inside the container.
- If sudo needs a password during install, set `SUDO_PASSWORD` (defaults to `123` inside the dev container).
- After installation, `/workspace/bin/freetube` overrides the system binary and launches FreeTube with `--no-sandbox` automatically, so the agent can start it without extra flags.
- Rebuild FreeTube even if it is already present with `FORCE_FREETUBE_INSTALL=1`.

- **What starts automatically:** `docker compose up` launches TurboVNC (display `:4`), the noVNC web proxy (port `6080`), the Ollama server, and runs `pip install -r computer-use-demo/computer_use_demo/requirements.txt` inside the container. Any apps listed in `INSTALL_APPS` are built/installed before the container drops into a shell.

- `cd ~/MCPWorld/docker`: Switch into the Docker folder that holds the compose file.
- `docker compose up -d`: Build (if needed) and start the services in detached mode so they run in the background.

## 2. Launch the Streamlit Control Panel

Use the bootstrap helper to start Streamlit (and any other requested services) from the repository root.

```bash
cd ~/MCPWorld
python3 tools/bootstrap_env.py start --only streamlit
```

- `cd ~/MCPWorld`: Return to the project root where the bootstrap script lives.
- `python3 tools/bootstrap_env.py start --only streamlit`: Launch only the Streamlit UI—everything else (VNC, noVNC, Ollama, etc.) is already running from Docker Compose. Drop `--only streamlit` if you ever need the bootstrapper to manage the full stack instead.


## 3. Initialize the Local LLM

Ollama is already running inside the container; pick the model you need and let the bootstrap script handle loading it.

```bash
cd ~/MCPWorld
python3 tools/manage_ollama_model.py \
  --model qwen2.5:7b-instruct \
  --pull \
  --show-status
```

- Common model targets: `qwen2.5:7b-instruct`, `qwen2.5:14b-instruct`, `llama3.2:3b-instruct`. Pass the model tag that matches your workflow.
- Swap `--pull` for `--no-pull` if you already have the weights cached; add `--stop-running` or `--evict-others` to free VRAM/disk from other models.
- The helper lives at `tools/manage_ollama_model.py`; run it any time you need to change models or inspect status (`--show-status` alone prints what’s installed and running).
- To remove a model entirely, call `ollama rm <model>` (e.g. `ollama rm qwen2.5:7b-instruct`) or invoke the helper with `ollama` directly after stopping the target (`--stop-target`) and pruning (`--prune`).

## 4. Monitor Headless Runs

When you execute tasks directly from the terminal (e.g., `run_pure_computer_use_with_eval.py`), the evaluator logs everything under the session folder you specify (default `logs/`). Tail the live log and inspect the saved metrics afterward:

```bash
# Watch the evaluator log as it streams (replace paths with your session)
tail -f logs/<timestamp>/<app>_<task>_evaluator.log
```

```bash
# After the run finishes, review the computed metrics and events
cat logs/<timestamp>/result_<app>_<task>_<timestamp>.json
```

- `tail -f …_evaluator.log`: Follow real-time output from the evaluator—tool calls, key-step hits, and final TASK_END status.
- `cat result_….json`: Dump the ResultCollector snapshot (success flag, duration, key-step coverage, token/tool stats). Load it into `jq`/Python for deeper analysis.
