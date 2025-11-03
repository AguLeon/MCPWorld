#!/bin/bash

cd /workspace/PC-Canary/apps/vscode/

npm cache clean --force
yarn run compile

# Add symbolic link to code-cli
sudo ln -sf /workspace/PC-Canary/apps/vscode/scripts/code-cli.sh /usr/local/bin/code
sudo chmod +x /workspace/PC-Canary/apps/vscode/scripts/code-cli.sh

# Run the code (Check if it works)
code --version
