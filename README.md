# MCPWorld: A Multi-Modal Test Platform for Computer-Using Agents (CUA)

## Pending stuff from AN-AL review:
 - Add table contents
 - Add a link to a sample json files (that looks nice)

![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Docker](https://img.shields.io/badge/Docker-Supported-green.svg)

MCPWorld is an open-source benchmarking framework designed for evaluating **Computer-Using Agents (CUAs)**. It supports agents that interact with software applications via **GUI**, **API (Model Context Protocol – MCP)**, or **Hybrid** methods.

---

## Key Features

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

## Overview
![Brief overview of this project](docs/mcpworld_system.png)

---

## Installation

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
## Quickstart

Kick off MCPWorld environment with the essentials below/ Each step explains what the command accomplishes so the system can be run with confidence. These can be done directly after cloning the repository and its sub-modules.

## 1. Start the Docker Workspace

Bring up the container stack defined in `docker-compose.yml`. This boots the desktop environment, VNC/noVNC services, Ollama, and prepares the shared workspace volume.

```bash
cd ~/MCPWorld/docker
docker compose up -d
```

- SUDO password for `mcpworld` environment : `123`

### **What starts automatically:**
`docker compose up` launches 2 containers; `mcpworld` and `ollama`:
- In `mcpworld` container, following are run automatically:
    - TurboVNC (display `:4`),
    - The noVNC web proxy (port `6080`),
    - Streamlit to demo LLM and agent's action (port 8501)
    - All the packages specified in `computer-use-demo/computer_use_demo/requirements.txt`
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

## Running Tests
After the environment, is created, necessary services are created, and the apps to be tested are installed, now is time to run the test!
There are 2 main ways it can be done:
- From the host machine
    - Running multiple tests across LLM models (`./scripts/run_multi_model_benchmark.sh`)
- From the docker container (`mcpworld`)
    - Running multiple tests for single LLM Model (`/workspace/scripts/run_tasks_range.sh`)
    - Running individual tests for single LLM models
        ```bash
        python3 computer-use-demo/run_pure_computer_use_with_eval.py \
        --provider "$PROVIDER" \
        --openai_api_key dummy \
        --openai_base_url "$OPENAI_BASE_URL" \
        --openai_endpoint "$OPENAI_ENDPOINT" \
        --model "$MODEL" \
        --task_id "$TASK_ID" \
        --log_dir "$RUN_LOG_DIR" \
        --exec_mode "$EXEC_MODE" \
        --timeout "$TASK_TIMEOUT" \
        --api_key "$ANTHROPIC_API_KEY"
        ```
- You can use the batch tests to run the entire benchmark suite while the individual tests is useful for debugging and testing various aspect of this project

---

## Documentation

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

## License

Released under the MIT License.

---
