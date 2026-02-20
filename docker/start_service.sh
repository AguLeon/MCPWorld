#!/bin/bash

# Ensure conda-installed tools (mcp-proxy, pip, etc.) are on PATH
export PATH="/home/agent/miniconda3/bin:$PATH"

# Setup VNC password
mkdir -p ~/.vnc
echo "12345678" | /opt/TurboVNC/bin/vncpasswd -f >~/.vnc/passwd
chmod 600 ~/.vnc/passwd

echo $WIDTH
echo $HEIGHT

echo "Starting container services..."

# Run the VNC Server
/opt/TurboVNC/bin/vncserver -xstartup ~/.vnc/xstartup -geometry ${WIDTH}x${HEIGHT} :4
echo "TurboVNC started!"

# Set display for all future processes
export DISPLAY=:4
export XAUTHORITY=/home/agent/.Xauthority

# Run the noVNC server (for web inteface)
/opt/noVNC/utils/novnc_proxy \
    --vnc localhost:5904 \
    --listen 0.0.0.0:6080 \
    --web /opt/noVNC >/tmp/novnc.log 2>&1 &
echo "noVNC server started!"

# Install Python Packages
/home/agent/miniconda3/bin/pip install -r /workspace/computer-use-demo/computer_use_demo/requirements.txt
echo "Python Packages installed!"

# Run streamlit headless
export STREAMLIT_BROWSER_GATHER_USAGE_STATS=false
export STREAMLIT_SERVER_HEADLESS=true
export STREAMLIT_SERVER_ADDRESS=0.0.0.0
export STREAMLIT_SERVER_PORT=8501

# Start Streamlit in background
cd /workspace/computer-use-demo
python -m streamlit run computer_use_demo/streamlit.py >/tmp/streamlit.log 2>&1 &
echo "$(</tmp/streamlit.log)"
echo "Streamlit Enable in port $STREAMLIT_SERVER_PORT!"

# Run streamlit headless
# NOTE: Running streamlit here caused unexpected issues, please run it from a bash session
# cd /workspace/computer-use-demo
# STREAMLIT_SERVER_HEADLESS=true STREAMLIT_SERVER_PORT=8501 python -m streamlit run computer_use_demo/streamlit.py >/tmp/streamlit.log 2>&1 &

cd /workspace
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

# Wait for background installers to finish before finishing startup so logs are complete.
wait

# Open the bash
exec bash
