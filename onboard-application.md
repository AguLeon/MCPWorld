# Onboard Applications
This guide covers the complete process of adding a new application for agent benchmarking and evaluation.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

  - [System Architecture Overview](#system-architecture-overview)
    - [Task File Structure](#task-file-structure)
  - [Part 1: Installing the Application](#part-1-installing-the-application)
    - [1.1 Container Environment](#11-container-environment)
    - [1.2 Installation Methods](#12-installation-methods)
      - [Method A: APT Package Manager](#method-a-apt-package-manager)
      - [Method B: Flatpak](#method-b-flatpak)
      - [Method C: Clone/Fork and Build (Developer Version)](#method-c-clonefork-and-build-developer-version)
      - [Method D: AppImage](#method-d-appimage)
    - [1.3 Making the Application Discoverable](#13-making-the-application-discoverable)
      - [1.5 Verification](#15-verification)
  - [Part 2: Adding Tasks and Evaluator](#part-2-adding-tasks-and-evaluator)
    - [2.1 Understanding Context Data](#21-understanding-context-data)
    - [2.2 Creating Task Directory Structure](#22-creating-task-directory-structure)
    - [2.3 Creating config.json](#23-creating-configjson)
    - [2.4 Creating handler.py](#24-creating-handlerpy)
    - [2.5 Creating hooker.js (Optional)](#25-creating-hookerjs-optional)
    - [2.6 Choosing the Right Evaluator Type](#26-choosing-the-right-evaluator-type)
    - [2.7 Adding MCP Support (Optional)](#27-adding-mcp-support-optional)
  - [Part 3: Testing Your Integration](#part-3-testing-your-integration)
    - [3.1 Manual Testing](#31-manual-testing)
    - [3.2 Run with Agent](#32-run-with-agent)
    - [3.3 Check Results](#33-check-results)
  - [Checklist for New Application Onboarding](#checklist-for-new-application-onboarding)
    - [Application Installation](#application-installation)
    - [Context Data](#context-data)
    - [Task Configuration](#task-configuration)
    - [Testing](#testing)
  - [Example: Complete Onboarding for a New App](#example-complete-onboarding-for-a-new-app)
    - [1. Installation Script](#1-installation-script)
    - [2. Context Data](#2-context-data)
    - [3. Task Config](#3-task-config)
    - [4. Handler](#4-handler)
  - [Key things to consider when on-boarding new applications](#key-things-to-consider-when-on-boarding-new-applications)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->
--- 
## System Architecture Overview

![Brief overview of this project](docs/mcpworld_system.png)

The OpenMCP evaluation system consists of four main components:
| Component       | Description                                                                                                   |
|-----------------|---------------------------------------------------------------------------------------------------------------|
| Task            | Contains config.json (parameters), hooker.js (internal state inspector), and handler.py (evaluation logic)    |
| Evaluator       | Parses config, collects information after agent calls, runs evaluation functions, outputs aggregated JSON logs |
| Client          | run_pure_computer_use_with_eval.py or streamlit.py – runs the agent loop and interfaces with the evaluator     |
| Agent & Model   | loop.py – starts MCP client, connects to servers, builds prompts, sends/parses LLM responses, executes tools   |

### Task File Structure
```
tests/tasks/{app_name}/{task_id}_{task_name}/
├── config.json      # Task parameters, prompts, ground truth, context data location
├── hooker.js        # (Optional) WebSocket connection to app internal state
└── handler.py       # Evaluation logic functions
```

---

## Part 1: Installing the Application
### 1.1 Container Environment
OpenMCP runs on Ubuntu 22.04 inside Docker containers. Applications must be installable and runnable within this environment.

### 1.2 Installation Methods
Choose the appropriate installation method for your application:

#### Method A: APT Package Manager

```bash
# Install from Ubuntu repositories
sudo apt-get update
sudo apt-get install -y <package-name>

# Example: Installing GIMP
sudo apt-get install -y gimp
```

#### Method B: Flatpak
```bash

# Install Flatpak if not present
sudo apt-get install -y flatpak

# Add Flathub repository
flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo

# Install application
flatpak install -y flathub <application-id>

# Example: Installing OBS Studio
flatpak install -y flathub com.obsproject.Studio
```

#### Method C: Clone/Fork and Build (Developer Version)
This is the recommended approach for applications that need instrumentation or modification for evaluation.
```bash
# Clone the repository
git clone https://github.com/<org>/<app-name>.git
cd <app-name>

# Or add as submodule to PC-Canary
cd PC-Canary/apps
git submodule add https://github.com/<org>/<app-name>.git

# Install build dependencies
sudo apt-get install -y <build-deps>

# Build the application (varies by project)
# Example for Node.js/Electron apps:
npm install
npm run compile

# Example for CMake projects:
mkdir build && cd build
cmake ..
make -j$(nproc)
```

Advantages of Developer Builds:
- Can add instrumentation hooks for evaluation
- Access to debug logging
- Can modify source for WebSocket/IPC integration

#### Method D: AppImage
```bash
# Download AppImage
wget https://example.com/app.AppImage -O /opt/app.AppImage

# Make executable
chmod +x /opt/app.AppImage

# Create wrapper script (see Section 1.3)
```

### 1.3 Making the Application Discoverable
After installation, ensure the agent/user can find the application using `which {app_name}`.

```bash
#!/bin/bash
set -e

# Download and install NoteTaker
wget -O /tmp/notetaker.AppImage "https://example.com/NoteTaker.AppImage"
mkdir -p /opt/notetaker
mv /tmp/notetaker.AppImage /opt/notetaker/
chmod +x /opt/notetaker/notetaker.AppImage

# Create wrapper with --no-sandbox
mkdir -p /workspace/bin
cat > /workspace/bin/notetaker << 'EOF'
#!/bin/bash
exec /opt/notetaker/notetaker.AppImage --no-sandbox "$@"
EOF
chmod +x /workspace/bin/notetaker

# Add to PATH
ln -sf /workspace/bin/notetaker /usr/local/bin/notetaker

echo "NoteTaker installed successfully!"
```

NOTE: The `--no-sandbox` Flag
Important: Many Electron/Chromium-based applications require the --no-sandbox flag to run properly in Docker:
```bash
# Without sandbox (required in Docker)
/path/to/app --no-sandbox

# Wrapper script handles this automatically
cat > /workspace/bin/myapp << 'EOF'
#!/bin/bash
exec /opt/myapp/myapp --no-sandbox "$@"
EOF
```

Applications typically requiring --no-sandbox:
- VSCode
- FreeTube
- Obsidian
- Slack
- Discord
- Any Electron-based app

#### 1.5 Verification
After installation, verify the application is properly set up:
```bash
# Check if discoverable
which myapp
# Expected: /usr/local/bin/myapp or /workspace/bin/myapp

# Test execution
myapp --version

# Test in VNC environment
export DISPLAY=:4
myapp &
```

---

## Part 2: Adding Tasks and Evaluator

### 2.1 Understanding Context Data
Context data simulates real-world application scenarios for consistent, reproducible evaluation.

What Context Data may include things such as:
| Type                 | Examples                                  | Purpose                              |
|----------------------|-------------------------------------------|--------------------------------------|
| User Settings        | Themes, preferences, keybindings          | Test settings modification tasks     |
| Plugins/Extensions   | Installed extensions, their configs       | Test extension management             |
| Project Files        | Documents, code files, media              | Test file operations                  |
| Application State    | Workspace configs, recent files           | Ensure consistent starting state      |
| User Data            | Profiles, accounts (sanitized)            | Test user-specific features           |

The context data varies between application, so make sure that the context data is correct and can be directly usable for the application

Context Data Location in this project
```code
PC-Canary/tests/context_data/
├── vscode/
│   ├── user_data_dir/           # VSCode user settings
│   │   ├── User/
│   │   │   ├── settings.json
│   │   │   └── keybindings.json
│   │   └── extensions/
│   └── C-Plus-Plus/             # Sample project files
│       └── sorting/
│           └── bubble_sort/
├── obsidian/
│   └── vault/                   # Obsidian vault with notes
│       ├── Ideas.md
│       └── .obsidian/
└── myapp/                       # Your app's context data
    ├── config/
    └── projects/
```

NOTE: Tasks may modify files during execution, so context data is copied to a working directory before each evaluation:
```JSON
{
  "context_data": [
    {
      "from": "tests/context_data/myapp/config",
      "to": "/workspace/.mcpworld/myapp/config"
    },
    {
      "from": "tests/context_data/myapp/projects",
      "to": "/workspace/.mcpworld/myapp/projects"
    }
  ]
}
```
The evaluator uses `rsync` to restore this data before each task run, ensuring a clean state.

### 2.2 Creating Task Directory Structure
```bash
# Create task directory
mkdir -p PC-Canary/tests/tasks/myapp/task01_exampleTask

# Create required files
touch PC-Canary/tests/tasks/myapp/task01_exampleTask/config.json
touch PC-Canary/tests/tasks/myapp/task01_exampleTask/handler.py
# Optional: touch PC-Canary/tests/tasks/myapp/task01_exampleTask/hooker.js
```


### 2.3 Creating config.json
The config file contains all task parameters as shown in the architecture diagram:
```JSON
{
  "description": "Create a new note titled 'Meeting Notes' in the Personal notebook",
  "instruction_template": "Open NoteTaker and create a new note titled '$note_title' in the '$notebook' notebook. Add the content: '$content'",
  "task_parameters": {
    "note_title": "Meeting Notes",
    "notebook": "Personal",
    "content": "Discussed project timeline"
  },
  "total_key_steps": 3,
  "application_info": {
    "executable_path": "/workspace/bin/notetaker",
    "args": []
  },
  "context_data": [
    {
      "from": "tests/context_data/notetaker/config",
      "to": "/workspace/.mcpworld/notetaker/config"
    },
    {
      "from": "tests/context_data/notetaker/notebooks",
      "to": "/workspace/.mcpworld/notetaker/notebooks"
    }
  ],
  "evaluation_setup": {
    "timeout": 180,
    "evaluator_type": "StateInspector",
    "evaluate_on_completion": true,
    "scripts": [{"role": "handler", "path": "handler.py"}]
  },
  "ground_truth": {
    "note_exists": true,
    "note_title": "Meeting Notes",
    "note_content_contains": "project timeline"
  }
}
```

Config Field Reference
| Field                 | Description                                                     |
|-----------------------|-----------------------------------------------------------------|
| description           | Human-readable task description                                 |
| instruction_template  | Prompt for the agent (supports `$variable` substitution)        |
| task_parameters       | Variables used in instruction template and evaluation            |
| total_key_steps       | Number of key steps to track                                     |
| application_info      | App executable path, arguments, working directory                |
| context_data          | Files to restore before each run                                 |
| evaluation_setup      | Timeout, evaluator type, scripts to use                          |
| files_to_check        | Files to inspect for evaluation                                  |
| ground_truth          | Expected values (label)                                          |
| mcp_servers           | MCP servers to connect (if app supports MCP)                     |

### 2.4 Creating handler.py
The handler contains the evaluation logic:
```python
#!/usr/bin/env python3
import os
from typing import Dict, Any, Optional, List

NOTEBOOKS_PATH = "/workspace/.mcpworld/notetaker/notebooks"
EXPECTED_NOTEBOOK = "Personal"
EXPECTED_TITLE = "Meeting Notes"
EXPECTED_CONTENT = "project timeline"

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global EXPECTED_NOTEBOOK, EXPECTED_TITLE, EXPECTED_CONTENT
    if task_parameter:
        EXPECTED_NOTEBOOK = task_parameter.get("notebook", EXPECTED_NOTEBOOK)
        EXPECTED_TITLE = task_parameter.get("note_title", EXPECTED_TITLE)
        EXPECTED_CONTENT = task_parameter.get("content", EXPECTED_CONTENT)

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_note_created"}, None)

def _evaluate_note() -> List[Dict[str, Any]]:
    results = []
    note_path = os.path.join(NOTEBOOKS_PATH, EXPECTED_NOTEBOOK, f"{EXPECTED_TITLE}.md")
    
    # Key Step 1: Note file exists
    if not os.path.exists(note_path):
        return [{"status": "error", "type": "note_missing", "message": f"Note not found: {note_path}"}]
    results.append({"status": "key_step", "index": 1})
    
    # Key Step 2: Read and verify content
    with open(note_path, "r") as f:
        content = f.read()
    results.append({"status": "key_step", "index": 2})
    
    # Key Step 3: Content contains expected text
    if EXPECTED_CONTENT.lower() in content.lower():
        results.append({"status": "key_step", "index": 3})
        results.append({"status": "success", "reason": "Note created with correct content"})
    else:
        results.append({"status": "error", "type": "content_mismatch", "message": "Expected content not found"})
    
    return results

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    event = message.get("event") or message.get("event_type")
    if event in ["evaluate_note_created", "evaluate_on_completion"]:
        return _evaluate_note()
    return None
```

### 2.5 Creating hooker.js (Optional)
```javascript
/**
 * WebSocket hook for MyApp internal state inspection.
 * Connects to the application to monitor state changes.
 */

// Socket connection is provided by the evaluator framework
// socket.on/socket.emit are available

/**
 * Called when evaluator requests state evaluation
 */
socket.on('evaluate', async () => {
    try {
        // Get current application state
        const currentState = await getAppState();
        
        // Send state to evaluator
        socket.emit("send", {
            'event_type': "evaluate_on_completion",
            'message': "Captured application state",
            'theme': currentState.theme,
            'settings': currentState.settings
        });
    } catch (error) {
        socket.emit("send", {
            'event_type': "error",
            'message': error.message
        });
    }
});

/**
 * Monitor real-time state changes
 */
function monitorStateChanges() {
    // Application-specific monitoring logic
    // This depends on how your app exposes its internal state
}

// Initialize monitoring when script loads
monitorStateChanges();
```


### 2.6 Choosing the Right Evaluator Type
| Evaluator Type  | Use Case                                           | Communication           |
|-----------------|----------------------------------------------------|--------------------------|
| StateInspector  | File-based evaluation, no app instrumentation needed | Filesystem inspection   |
| HookManager     | Frida-based hooking into native apps               | Frida scripts            |
| IpcInjector     | Electron/Node apps with Socket.IO support          | WebSocket / Socket.IO   |

```JSON
{
  "evaluation_setup": {
    "evaluator_type": "StateInspector"  // or "HookManager" or "IpcInjector"
  }
}
```

### 2.7 Adding MCP Support (Optional)
If your application has an MCP server, configure it in the task:

```JSON
{
  "mcp_servers": [
    {
      "command": "uvx",
      "args": ["mcp-myapp"],
      "env": {
        "MYAPP_API_KEY": "your-api-key",
        "MYAPP_HOST": "http://127.0.0.1",
        "MYAPP_PORT": "8080"
      }
    }
  ]
}
```

---

## Part 3: Testing Your Integration
### 3.1 Manual Testing
```bash
# Enter the container
docker exec -it mcpworld /bin/bash

# Set display
export DISPLAY=:4

# Test application launch
which myapp
myapp --no-sandbox &

# Test evaluator standalone
cd /workspace/PC-Canary
python run_evaluator.py --app myapp --task task01_exampleTask
```

### 3.2 Run with Agent
```bash
# From inside container
python computer-use-demo/run_pure_computer_use_with_eval.py \
  --provider openai \
  --openai_api_key dummy \
  --openai_base_url http://host.docker.internal:11434 \
  --model qwen3-vl:32b \
  --task_id myapp/task01_exampleTask \
  --log_dir logs_computer_use_eval \
  --exec_mode mixed \
  --timeout 180
```

### 3.3 Check Results
```bash
# View logs
tail -f logs_computer_use_eval/<timestamp>/myapp_task01_exampleTask_evaluator.log

# Review results
cat logs_computer_use_eval/<timestamp>/result_myapp_task01_*.json | jq .
```

---

## Checklist for New Application Onboarding
### Application Installation
- [ ] Application runs on Ubuntu 22.04
- [ ] Installation script created in `docker/apps_install_scripts/`
- [ ] Wrapper script with `--no-sandbox` if needed
- [ ] Symbolic link or PATH entry created
- [ ] `which app_name` returns correct path
- [ ] Application launches in VNC environment

### Context Data
- [ ] Context data directory created in `tests/context_data/myapp/`
- [ ] User settings/preferences included
- [ ] Sample project files if needed
- [ ] Plugins/extensions configured

### Task Configuration
- [ ] Task directory structure: `tests/tasks/myapp/task01_*/`
- [ ] `config.json` with all required fields
- [ ] `handler.py` with evaluation logic
- [ ] `hooker.js` if using WebSocket/IPC (optional)
- [ ] Correct evaluator type selected

### Testing
- [ ] Manual application test passes
- [ ] Standalone evaluator test passes
- [ ] Full agent + evaluator test passes
- [ ] Results JSON generated correctly

---

## Example: Complete Onboarding for a New App
This is the process to onboarding a hypothetical "NoteTaker" application:

### 1. Installation Script
```bash
#!/bin/bash
set -e

# Download and install NoteTaker
wget -O /tmp/notetaker.AppImage "https://example.com/NoteTaker.AppImage"
mkdir -p /opt/notetaker
mv /tmp/notetaker.AppImage /opt/notetaker/
chmod +x /opt/notetaker/notetaker.AppImage

# Create wrapper with --no-sandbox
mkdir -p /workspace/bin
cat > /workspace/bin/notetaker << 'EOF'
#!/bin/bash
exec /opt/notetaker/notetaker.AppImage --no-sandbox "$@"
EOF
chmod +x /workspace/bin/notetaker

# Add to PATH
ln -sf /workspace/bin/notetaker /usr/local/bin/notetaker

echo "NoteTaker installed successfully!"
```


### 2. Context Data
```
tests/context_data/notetaker/
├── config/
│   └── settings.json
└── notebooks/
    ├── Personal/
    │   └── Ideas.md
    └── Work/
        └── Tasks.md
```


### 3. Task Config
```JSON
{
  "description": "Create a new note titled 'Meeting Notes' in the Personal notebook",
  "instruction_template": "Open NoteTaker and create a new note titled '$note_title' in the '$notebook' notebook. Add the content: '$content'",
  "task_parameters": {
    "note_title": "Meeting Notes",
    "notebook": "Personal",
    "content": "Discussed project timeline"
  },
  "total_key_steps": 3,
  "application_info": {
    "executable_path": "/workspace/bin/notetaker",
    "args": []
  },
  "context_data": [
    {
      "from": "tests/context_data/notetaker/config",
      "to": "/workspace/.mcpworld/notetaker/config"
    },
    {
      "from": "tests/context_data/notetaker/notebooks",
      "to": "/workspace/.mcpworld/notetaker/notebooks"
    }
  ],
  "evaluation_setup": {
    "timeout": 180,
    "evaluator_type": "StateInspector",
    "evaluate_on_completion": true,
    "scripts": [{"role": "handler", "path": "handler.py"}]
  },
  "ground_truth": {
    "note_exists": true,
    "note_title": "Meeting Notes",
    "note_content_contains": "project timeline"
  }
}
```
### 4. Handler
```python
#!/usr/bin/env python3
import os
from typing import Dict, Any, Optional, List

NOTEBOOKS_PATH = "/workspace/.mcpworld/notetaker/notebooks"
EXPECTED_NOTEBOOK = "Personal"
EXPECTED_TITLE = "Meeting Notes"
EXPECTED_CONTENT = "project timeline"

def _update_params(task_parameter: Dict[str, Any]) -> None:
    global EXPECTED_NOTEBOOK, EXPECTED_TITLE, EXPECTED_CONTENT
    if task_parameter:
        EXPECTED_NOTEBOOK = task_parameter.get("notebook", EXPECTED_NOTEBOOK)
        EXPECTED_TITLE = task_parameter.get("note_title", EXPECTED_TITLE)
        EXPECTED_CONTENT = task_parameter.get("content", EXPECTED_CONTENT)

def inspector_on_completion(eval_handler):
    eval_handler({"event": "evaluate_note_created"}, None)

def _evaluate_note() -> List[Dict[str, Any]]:
    results = []
    note_path = os.path.join(NOTEBOOKS_PATH, EXPECTED_NOTEBOOK, f"{EXPECTED_TITLE}.md")
    
    # Key Step 1: Note file exists
    if not os.path.exists(note_path):
        return [{"status": "error", "type": "note_missing", "message": f"Note not found: {note_path}"}]
    results.append({"status": "key_step", "index": 1})
    
    # Key Step 2: Read and verify content
    with open(note_path, "r") as f:
        content = f.read()
    results.append({"status": "key_step", "index": 2})
    
    # Key Step 3: Content contains expected text
    if EXPECTED_CONTENT.lower() in content.lower():
        results.append({"status": "key_step", "index": 3})
        results.append({"status": "success", "reason": "Note created with correct content"})
    else:
        results.append({"status": "error", "type": "content_mismatch", "message": "Expected content not found"})
    
    return results

def message_handler(message: Dict[str, Any], logger, task_parameter: Dict[str, Any]) -> Optional[List[Dict[str, Any]]]:
    _update_params(task_parameter)
    event = message.get("event") or message.get("event_type")
    if event in ["evaluate_note_created", "evaluate_on_completion"]:
        return _evaluate_note()
    return None
```

---

## Key things to consider when on-boarding new applications
1. Consistent Installation: Ensure applications are discoverable via which
2. Docker Compatibility: Use --no-sandbox for Electron apps
3. Context Data: Provide realistic, restorable application states
4. Modular Evaluation: Separate configuration, hooking, and evaluation logic
