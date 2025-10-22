#! /bin/bash

cd ../../PC-Canary/apps/vscode/

yarn run compile

./scripts/code.sh --no-sandbox
