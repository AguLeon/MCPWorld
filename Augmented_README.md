# MCPWorld: A Multi-Modal Test Platform for Computer-Using Agents (CUA)
![License](https://img.shields.io/badge/license-MIT-blue.svg) ![Docker](https://img.shields.io/badge/Docker-Supported-green.svg)

MCPWorld is an open-source benchmarking framework designed for evaluating **Computer-Using Agents (CUAs)**. It supports agents that interact with software applications via **GUI**, **API (Model Context Protocol – MCP)**, or **Hybrid** methods.

---

## 🚀 Key Features

- **Comprehensive Task Suite** – ~170 tasks across 10+ open-source applications (VSCode, OBS, Zotero, etc.).
- **GUI, API, and Hybrid Interaction** – Integrated MCP support enables robust mixed-mode control, letting agents fall back to GUI when APIs are unavailable.
- **White-Box Evaluation** – Built-in evaluators inspect internal app signals or outputs for precise, reproducible task verification.
- **Cross-Platform via Docker** – Containerized environments ensure consistent setups on Linux, macOS, and Windows.
- **Extensible Framework** – Easily add new tasks, applications, or custom agents via clear folder structure and interfaces.

---

## 📦 Installation

### Prerequisites
- Docker
- (Optional) VS Code + DevContainers extension

### Quick Setup
```bash
git clone https://github.com/SAAgent/MCPWorld.git
cd MCPWorld
git submodule update --init PC-Canary
```

Then open the folder in VS Code and select **Reopen in Container**, or manually build the image according to the Dockerfile provided by PC-Canary:

```bash
docker build -f PC-Canary/.devcontainer/Dockerfile -t mcpworld:pc-canary .
```

---

## 🚩 Quickstart

### 🚀 Running the Interactive Agent Demo with Evaluation

These instructions assume you are running commands inside the container.

#### Install Dependencies
```bash
pip install -r computer-use-demo/computer_use_demo/requirements.txt
```
> ⚠ If network fails due to a stale proxy in the image, unset it first:  
> `unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY`

#### Start Required Services (each in its own terminal)
- **VNC Server**
```bash
vncserver -xstartup ~/.vnc/xstartup -geometry 1024x768 :4
```
Accessible on port 5904 (raw VNC).

- **noVNC Proxy**
```bash
/opt/noVNC/utils/novnc_proxy   --vnc localhost:5904   --listen 0.0.0.0:6080   --web /opt/noVNC > /tmp/novnc.log 2>&1 &
```
Accessible at: `http://<VM-IP>:6080/vnc.html`

- **Main HTTP Server**
```bash
python computer-use-demo/image/http_server.py > /tmp/http_server.log 2>&1 &
```
Accessible at: `http://<VM-IP>:8081`

- **Streamlit Agent & Evaluator UI**
```bash
cd computer-use-demo
STREAMLIT_SERVER_PORT=8501 python -m streamlit run computer_use_demo/streamlit.py > /tmp/streamlit.log 2>&1 &
```
Accessible at: `http://<VM-IP>:8501`

#### Accessing the Demo
- Unified Interface: `http://<VM-IP>:8081`
- VNC Desktop (via browser): `http://<VM-IP>:6080`
- Agent & Evaluator UI (Streamlit): `http://<VM-IP>:8501`

---

### 🧪 Headless Agent & Evaluator Execution (CLI-Only)

Run without UI:

```bash
python computer-use-demo/run_pure_computer_use_with_eval.py   --api_key "$ANTHROPIC_API_KEY"   --model claude-3-7-sonnet-20250219   --task_id telegram/task01_search   --log_dir logs_computer_use_eval   --exec_mode mixed
```

---

## ⚡ Practical Setup Notes & Troubleshooting

During real deployments, several issues can arise. Below are the solutions we applied:

### Python Environment
- Prefer a venv under home to avoid permission issues:
  ```bash
  python3 -m venv ~/venv
  source ~/venv/bin/activate
  ```
- Proxy environment variables baked into the Docker image often break installs. Fix with:
  ```bash
  unset http_proxy https_proxy HTTP_PROXY HTTPS_PROXY
  ```

### Anthropic / MCP SDK Compatibility
- New versions renamed **beta types**. Fixes include:
  - Add `is_timeout=False` when calling `sampling_loop(...)`.
  - Replace `BetaContentBlockParam` → `ContentBlockParam`, `BetaToolUnionParam` → `ToolUnionParam`.
- If import errors persist, shim imports:
  ```python
  try:
      from anthropic.types.beta import BetaToolUnionParam
  except ImportError:
      from anthropic.types.tool_types import ToolUnionParam as BetaToolUnionParam
  ```

### Dependencies
- **Streamlit missing**: `pip install streamlit`
- **mcp not found**: `pip install mcp`
- **frida not found**: `pip install frida`

### uv Dependency
- Some tasks expect `uv`. Install inside container:
  ```bash
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
  ```

### API Keys
- Always use: `--api_key "$ANTHROPIC_API_KEY"`
- For Telegram tasks, also export:
  ```bash
  export TELEGRAM_API_ID=<your_id>
  export TELEGRAM_API_HASH=<your_hash>
  ```

### Applications
- **Third-party apps are not bundled**. You must install them in the container and set paths:
  - Example for FreeTube:
    ```bash
    sudo apt-get update && sudo apt-get install -y libfuse2
    mkdir -p /opt/apps/freetube && cd /opt/apps/freetube
    curl -L -o FreeTube.AppImage <FREETUBE_URL>
    chmod +x FreeTube.AppImage
    export FREETUBE_APP=/opt/apps/freetube/FreeTube.AppImage
    ```

### Ports
- `6080`: browser VNC (noVNC)
- `5904`: raw VNC (native client)
- `8081`: landing HTTP page
- `8501`: Streamlit

### Common Errors & Fixes
| Problem | Symptom | Fix |
|---------|---------|-----|
| Proxy errors | pip timeouts, 10.29.46.139 | `unset http_proxy https_proxy` |
| Anthropic import errors | Missing Beta types | Shim imports / patch code |
| frida missing | `ModuleNotFoundError: frida` | `pip install frida` |
| uv missing | `[Errno 2] No such file or directory: 'uv'` | Install uv and add PATH |
| pid None | `'NoneType'.pid` error | Install app and export path (e.g., FreeTube) |
| Telegram crash | `int() argument must be... NoneType` | Export Telegram API ID and hash |
| Streamlit errors | mismatched SDKs | Patch beta imports, add is_timeout param |

---

## 📚 Documentation

- **Tasks**: See `PC-Canary/tests/tasks/` for JSON/JS/Python configs.
- **Agents**: Reference implementations in `computer-use-demo/`.
- **Extension**: Add new apps/tasks/agents as described in docs.
- **Evaluation**: White-box evaluators guarantee objective metrics.

---

## 📝 License

Released under the MIT License.
