#! /bin/bash

cd /workspace/PC-Canary/apps/vscode/

npm cache clean --force
yarn run compile

./scripts/code.sh --no-sandbox
