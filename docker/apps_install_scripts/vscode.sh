#!/bin/bash

echo "Installing system dependencies..."
apt-get update
apt-get install -y \
    build-essential \
    libx11-dev \
    libxkbfile-dev \
    libsecret-1-dev \
    pkg-config

cd /workspace/PC-Canary/apps/vscode/

echo "Cleaning the npm cache"
npm cache clean --force

echo "Installing required packages"
npm install

echo "Compiling VSCode"
npm run compile

# Add symbolic links to both locations
ln -sf /workspace/PC-Canary/apps/vscode/scripts/code.sh /usr/local/bin/code
mkdir -p /usr/share/code
ln -sf /workspace/PC-Canary/apps/vscode/scripts/code.sh /usr/share/code/code
chmod +x /workspace/PC-Canary/apps/vscode/scripts/code.sh

# Run the code (Check if it works)
# code --version >>/tmp/vscode_install.log 2>&1 &
