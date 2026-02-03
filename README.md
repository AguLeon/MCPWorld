# MCPWorld: A Multi-Modal Test Platform for Computer-Using Agents (CUA)

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Docker](https://img.shields.io/badge/Docker-Supported-green.svg)

MCPWorld is an open-source benchmarking framework designed for evaluating **Computer-Using Agents (CUAs)**. It supports agents that interact with software applications via **GUI**, **API (Model Context Protocol – MCP)**, or **Hybrid** methods.

---

## 🚀 Key Features

* **Comprehensive Task Suite**

  * \~30+ tasks across multiple applications (VSCode, Obsidian).

* **GUI, API, and Hybrid Interaction**

  * Integrated MCP support enables robust mixed-mode control, letting agents fall back to GUI when APIs are unavailable.

* **Black and White-Box Evaluation**

  * Easily expandable evaluators for black-box testing
  * Built-in evaluators inspect internal app signals or outputs for precise, reproducible task verification.

* **Cross-Platform via Docker**

  * Containerized environments ensure consistent setups on Linux, macOS, and Windows.

* **Extensible Framework**

  * Easily add new tasks, applications, or custom agents via clear folder structure and interfaces.

---

## 📦 Installation

### Prerequisites

* Docker
* (Optional) VS Code + DevContainers extension

### Quick Setup

```bash
git clone https://github.com/AguLeon/MCPWorld
cd MCPWorld
git submodule update --init PC-Canary
```

We also want to clone downstream linked repositories to the open-source apps we use (e.g. VS Code):
```bash
git submodule update --init --recursive
```

Then open the folder in VS Code and select **Reopen in Container**

---
## 🚩 Quickstart

Kick off MCPWorld environment with the essentials below/ Each step explains what the command accomplishes so the system can be run with confidence. These can be done directly after cloning the repository and its sub-modules.

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

- Supported values today: `vscode`, `obsidian`.
- Installers run during container startup; logs land in `/tmp/obsidian_install.log` or `/tmp/vscode_install.log` inside the container.
- If sudo needs a password during install, set `SUDO_PASSWORD` (defaults to `123` inside the dev container).

### **What starts automatically:**
`docker compose up` launches 2 containers; `mcpworld` and `ollama`:
- In `mcpworld` container, following are run automatically:
    - TurboVNC (display `:4`),
    - The noVNC web proxy (port `6080`),
    - Streamlit to demo LLM and agent's action (port 8501)
    - All the packages specified in `computer-use-demo/computer_use_demo/requirements.txt`
    - Any apps listed in `INSTALL_APPS` in `docker/docker-compose.yml` are built/installed
- The `ollama` container runs a Ollama server

#### NOTE:
To go inside the docker container environment, you can write the following command:
```bash
docker exec -it <container-name> /bin/bash
```
This starts a container's bash session.

## 2. Install the apps to be tested(Inside `mcpworld` container)
- We have installation scripts for apps inside of ./docker/apps_install_scripts/*
    - Current list: vscode, obsidian
    - Run the script to install the applications. `./docker/apps_install_scripts/obsidian.sh`
    - The script will install the app and create a symbolic link for easy app startup

## 3. Test multiple Ollama automatically (In Host machine)
- The script to run the test is in `./scripts/run_multi_model_benchmark.sh <app-name> <infrastructure>`
    - E.g. of infrastructure: H100x1, RasberryPi5, CPU32GB, H100x4, etc.
- You can modify the models list all the models to test
```bash
MODELS=(
    ... # Add all the models to test (Must be available in ollama registry!)
)
```
- The model list is in `./scripts/models.cfg`
- Common model targets: `qwen3-vl:8b-instruct`, `qwen3:32b-instruct`, `ministral-3:14b`.
- Modify the configuration of the tests from: `./scripts/config.cfg`. Some the parameters are
    - Temperature
    - Timeout limit
    - LLM API Endpoint
    - Execution mode (api/gui/mixed)

## 4. Monitor Headless Runs
- The evaluator logs everything under the session folder you specify (default `logs_computer_use_eval/`). Tail the live log and inspect the saved metrics afterward:

```bash
# Watch the evaluator log as it streams (replace paths with your session)
tail -f logs_computer_use_eval/<app-name>_runs/<model-name>_<infrastructure>/<task-id>_<task_name>_evaluator/*.log
```

```bash
# After the run finishes, review the computed metrics and events
cat logs_computer_use_eval/<app-name>_runs/<model-name>_<infrastructure>/result_<timestamp>_<model>_<infrastructure>_<task-id>_<task_name>/*.json
```

- `tail -f …_evaluator.log`: Follow real-time output from the evaluator—tool calls, key-step hits, and final TASK_END status.
- `cat result_….json`: Dump the ResultCollector snapshot (success flag, duration, key-step coverage, token/tool stats). Load it into `jq`/Python for deeper analysis.

---

## 📚 Documentation

* **Manual Environment Setup**: To see how the environment is set-up step by step, see 
* **Tasks**: See `PC-Canary/tests/tasks/` for JSON/JS/Python configs.
* **Agents**: Reference implementations in `computer-use-demo/`.
* **Extension**: Add new apps/tasks/agents as described in docs (Update in progress).
* **Evaluation**: Black-box and White-box evaluators guarantee objective metrics.

---

<!-- ## 📖 Citation

```bibtex
@inproceedings{MCPWorld2025,
  title     = {MCPWorld: A Multi-Modal Test Platform for Computer-Using Agents},
  author    = {YourName and Author1 and Author2},
  booktitle = {NeurIPS 2025},
  year      = {2025}
}
``` -->

<!-- --- -->

## 📝 License

Released under the MIT License.

---

# Troubleshooting & Midsteps

This section collects the troubleshooting steps and commands we used while getting the repository running. Each command is annotated with **where it should be executed**.


## Environment Setup

- **Activate virtual environment (inside container, repo root):**

```bash
source venv/bin/activate
```

- **If using Conda base + venv (inside container):**

```bash
(venv) (base) agent@container:/workspace$ 
```


## Dependency Installation

- **Install requirements (from repo root inside container):**

```bash
pip install -r computer-use-demo/requirements.txt
```

- **Reinstalling specific versions of Anthropics/mcp:**

```bash
pip uninstall -y anthropic mcp
pip install --upgrade anthropic mcp
```

- **Check versions (inside container):**

```bash
python - <<'PY'
import anthropic, mcp
print('anthropic:', getattr(anthropic, '__version__','?'))
print('mcp:', getattr(mcp, '__version__','?'))
PY
```


## Running noVNC

- **Start noVNC server (inside container):**

```bash
/usr/share/novnc/utils/novnc_proxy --vnc localhost:5904
```

- You will see logs like:

```
WebSocket server settings:
  - Listen on 0.0.0.0:6080
  - proxying from 0.0.0.0:6080 to localhost:5904
```


## Streamlit Debugging

- **Launch Streamlit manually (inside repo root in container):**

```bash
STREAMLIT_SERVER_PORT=8501 python -m streamlit run computer_use_demo/streamlit.py > /tmp/streamlit.log 2>&1 &
```

- **Follow logs (inside container):**

```bash
tail -f /tmp/streamlit.log
```


## Common Errors & Fixes

- **ModuleNotFoundError (e.g., `mcp`, `frida`):**
  → Ensure requirements are installed with `pip install -r ...` inside the container.

- **ImportError with anthropic beta types:**
  → Fixed by upgrading to latest `anthropic` and `mcp` instead of pinning old versions.

- **Error: `[Errno 2] No such file or directory: 'uv'`:**
  → Install uv inside container:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"
```

- **TypeError: `int() argument must be a string, not NoneType` (Telegram API ID/Hash missing):**
  → Export credentials before running:

```bash
export TELEGRAM_API_ID=xxxx
export TELEGRAM_API_HASH=yyyy
```

- **Task missing `config.json`:**
  → Ensure you run with correct task IDs. Example working ones:

```bash
python computer-use-demo/run_pure_computer_use_with_eval.py \
  --api_key $ANTHROPIC_KEY \
  --model claude-3-7-sonnet-20250219 \
  --task_id FreeTube/task01_search \
  --log_dir logs_computer_use_eval \
  --exec_mode mixed
```

