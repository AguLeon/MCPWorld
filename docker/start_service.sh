#!/bin/bash

# Setup VNC password
mkdir -p ~/.vnc
echo "12345678" | /opt/TurboVNC/bin/vncpasswd -f >~/.vnc/passwd
chmod 600 ~/.vnc/passwd

# Run the VNC Server
/opt/TurboVNC/bin/vncserver -xstartup ~/.vnc/xstartup -geometry 1024x768 :4

# Run the noVNC server (for web inteface)
/opt/noVNC/utils/novnc_proxy \
    --vnc localhost:5904 \
    --listen 0.0.0.0:6080 \
    --web /opt/noVNC >/tmp/novnc.log 2>&1 &

# Run the MCP proxy (provides SSE bridge for MCP servers)
if [[ "${ENABLE_MCP_PROXY:-1}" != "0" ]]; then
  if [[ -x "$(command -v mcp-proxy)" ]]; then
    if ! timeout 1 bash -c "</dev/tcp/127.0.0.1/6010" &>/dev/null; then
      echo "[start_service] Starting MCP proxy on 0.0.0.0:6010"
      mcp-proxy --host=0.0.0.0 --port 6010 uvx mcp-server-fetch >/tmp/mcp_proxy.log 2>&1 &
    else
      echo "[start_service] MCP proxy already listening on 6010, skipping autostart."
    fi
  else
    echo "[start_service] Warning: mcp-proxy binary not found; MCP tasks may fail to connect."
  fi
fi

# Run the ollama server
ollama serve >/tmp/ollama.log 2>&1 &

# Install Python Packages
/home/agent/miniconda3/bin/pip install -r /workspace/computer-use-demo/computer_use_demo/requirements.txt

INSTALL_APPS_CSV="${INSTALL_APPS:-}"
mkdir -p /workspace/bin
export PATH="/workspace/bin:$PATH"
should_install() {
  local app="$1"
  [[ -z "$INSTALL_APPS_CSV" ]] && return 1
  IFS=',' read -ra items <<< "$INSTALL_APPS_CSV"
  for item in "${items[@]}"; do
    if [[ "${item,,}" == "${app,,}" ]]; then
      return 0
    fi
  done
  return 1
}

if should_install "freetube"; then
  bash /workspace/docker/apps_install_scripts/freetube.sh >/tmp/freetube_install.log 2>&1 &
fi
if should_install "vscode"; then
  bash /workspace/docker/apps_install_scripts/vscode.sh >/tmp/vscode_install.log 2>&1 &
fi
# Wait for background installers to finish before finishing startup so logs are complete.
wait

# Open the bash
exec bash
