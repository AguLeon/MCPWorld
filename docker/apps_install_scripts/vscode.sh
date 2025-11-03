#!/bin/bash

echo "Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
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

# yarn run compile

echo "Compiling VSCode"
npm run compile

# Add symbolic link to code-cli
sudo ln -sf /workspace/PC-Canary/apps/vscode/scripts/code-cli.sh /usr/local/bin/code
sudo chmod +x /workspace/PC-Canary/apps/vscode/scripts/code-cli.sh

# Run the code (Check if it works)
code --version
