# Obsidian Onboarding Log

This document tracks all actions taken to onboard Obsidian as a benchmarkable application in MCPWorld.

---

## 1. Application Installation Setup

### Script: `docker/apps_install_scripts/obsidian.sh`

**Purpose:** Automates the installation of Obsidian v1.7.7 inside the MCPWorld Docker environment (noVNC desktop).

**What the script does:**

1. **Install dependencies** (lines 4-5)
   - Updates apt package list
   - Installs `fuse` and `libfuse2` (required for AppImage execution)

2. **Download Obsidian AppImage** (line 8)
   - Fetches Obsidian v1.7.7 AppImage from official GitHub releases
   - Saves to `~/Obsidian.AppImage`

3. **Make executable** (line 10)
   - Sets execute permissions on the AppImage

4. **Extract AppImage** (lines 13-15)
   - Extracts the AppImage contents to `~/squashfs-root/`
   - This is necessary because AppImages need special handling in containerized environments

5. **Create global wrapper script** (lines 19-21)
   - Creates `/usr/local/bin/obsidian` wrapper script
   - Adds `--no-sandbox` flag (required for running Electron apps in Docker/noVNC)
   - Makes Obsidian available system-wide for the agent

6. **Create bash alias** (lines 24-25)
   - Adds convenience alias to `~/.bashrc`
   - Ensures `--no-sandbox` flag is always applied

7. **Return to workspace** (line 27)
   - Changes directory back to `/workspace`

**How to call it:**

```bash
# From within the MCPWorld Docker container
cd /home/cc/MCPWorld
bash docker/apps_install_scripts/obsidian.sh
```

**Expected outcome:**
- Obsidian installed and extracted to `~/squashfs-root/` (for the user running the install script)
- Global command `obsidian` available
- Application can be launched with: `obsidian` or `/usr/local/bin/obsidian`

**Notes:**
- The `--no-sandbox` flag is critical for Electron apps in Docker environments
- Similar pattern used in FreeTube installation (see `freetube.sh`)
- AppImage extraction is necessary because FUSE may not work properly in some container setups
- **Important:** The wrapper script path must match where the AppImage was extracted
  - If installed as `/home/agent`, the wrapper should reference `/home/agent/squashfs-root/obsidian`
  - The script uses `~` which expands differently depending on the user context
  - Verify the wrapper points to the correct absolute path after installation

---

## 2. MCP Server Integration

### Obsidian MCP Server

**Package:** `mcp-obsidian` (via `uvx`)

**Configuration:**
- **API Key:** `1234` (placeholder for local testing)
- **Host:** `http://127.0.0.1`
- **Port:** `27123`

**Available Tools:** See [PC-Canary/tests/tasks/obsidian/MCP_TOOLS_REFERENCE.md](PC-Canary/tests/tasks/obsidian/MCP_TOOLS_REFERENCE.md)

The MCP server provides programmatic access to Obsidian vault operations:
- File listing (`obsidian_list_files_in_vault`, `obsidian_list_files_in_dir`)
- File operations (`obsidian_get_file_contents`, `obsidian_append_content`, `obsidian_delete_file`)
- Search capabilities (`obsidian_simple_search`, `obsidian_complex_search`)
- Content modification (`obsidian_patch_content`)
- Periodic notes and recent changes tracking

---

## 3. Task Creation: task01_createNote

### Location
[PC-Canary/tests/tasks/obsidian/task01_createNote/](PC-Canary/tests/tasks/obsidian/task01_createNote/)

### Task Description
The first Obsidian task tests the most basic operation: creating a new note in the vault.

**Goal:** Agent must create a note named `TestNote.md` in the Obsidian vault.

### Files Created

#### 1. `config.json`
Defines the task configuration:
- **Evaluator Type:** `StateInspector` (not `IpcInjector`)
  - Why? We don't have access to Obsidian's source code to inject hooks
  - Instead, we use the MCP server API to inspect vault state
- **Application Info:**
  - `executable_path`: `"/usr/local/bin/obsidian"` - Direct path to Obsidian wrapper
  - `args`: `[]` - No arguments (Obsidian opens last vault by default)
  - The vault path is provided via the instruction template and task parameters
- **MCP Server:** Connects to `mcp-obsidian` with local configuration
- **Task Parameters:**
  - `note_name`: `TestNote.md`
  - `vault_path`: `/workspace/.mcpworld/obsidian/vault`
- **Key Steps:** 1 (note created in vault)
- **Context Data:** Copies `sample-vault` to `/workspace/.mcpworld/obsidian/vault`
  - This provides a pre-configured playground vault
  - Contains sample notes: `Welcome.md`, `Test Note 1.md`, etc.
  - Includes `.obsidian` configuration folder

#### 2. `handler.py`
Implements evaluation logic using **filesystem checks** (simplified approach):

**Key Functions:**
- `inspector_on_start()`: No-op for this task
- `inspector_on_completion(eval_handler)`: Called when task ends, verifies note exists via filesystem
- `message_handler()`: Dummy handler to satisfy BaseEvaluator (prevents warning)

**Evaluation Flow:**
1. Task completes
2. `inspector_on_completion()` is triggered
3. Check if file exists: `os.path.exists("/workspace/.mcpworld/obsidian/vault/TestNote.md")`
4. Report success/failure via `eval_handler`

**Why filesystem instead of MCP for evaluation?**
- Simpler and more direct
- MCP client requires async context (complex for StateInspector's sync callbacks)
- Filesystem check is just as reliable for verifying file creation
- Agent still uses MCP tools to *create* the note - only evaluation is filesystem-based

**Key Difference from VSCode:**
- VSCode: Injects JavaScript (`hooker.js`) into the app, receives events via IPC
- Obsidian: Uses filesystem check to verify final state (no code injection)

---

## 4. Key Architectural Differences

### VSCode Tasks (IpcInjector)
```
VSCode App (modified source)
  └─> hooker.js (injected) ──socket.io──> handler.py
                                           └─> Evaluates events
```

### Obsidian Tasks (StateInspector)
```
Obsidian App (unmodified)
  ├─> Agent uses MCP Server (mcp-obsidian) to create notes
  │     └─> Local API on port 27123
  │
  └─> Evaluator checks filesystem directly
        └─> handler.py: os.path.exists(vault_path/note.md)
```

**Advantages of StateInspector approach:**
- No need for application source code
- Works with any app that exposes an API or MCP server
- Cleaner separation between app and evaluator
- Can verify state at any time, not just on events

**Disadvantages:**
- Cannot track intermediate steps (only final state)
- Relies on external API availability
- Slightly higher latency for verification

---

## Next Steps

- [x] ~~Test Obsidian launch in noVNC environment~~
- [x] ~~Determine task scenarios for benchmarking~~
- [x] ~~Create MCP server for Obsidian (using existing `mcp-obsidian`)~~
- [x] ~~Write task configurations in `PC-Canary/tests/tasks/obsidian/`~~
- [x] ~~Implement evaluator handlers~~
- [x] ~~Fix all Chinese error messages in evaluator code~~
- [x] ~~Fix Obsidian wrapper script path~~
- [x] ~~Update config to use Obsidian URI protocol~~
- [ ] Test task01 with both API and mixed execution modes
- [ ] Create vault initialization setup
- [ ] Add context data for more complex tasks
- [ ] Implement additional tasks (task02, task03, etc.)

---

## Fixes Applied (2025-12-01)

### Fix 1: Obsidian Wrapper Script Path
**Issue:** The wrapper at `/usr/local/bin/obsidian` referenced `~/squashfs-root/obsidian`, but the AppImage was extracted to `/home/agent/squashfs-root/`

**Solution:** Updated wrapper to use absolute path:
```bash
#!/bin/bash
/home/agent/squashfs-root/obsidian --no-sandbox "$@"
```

### Fix 2: Chinese Error Messages Removed
**Files modified:**
- [PC-Canary/evaluator/core/state_inspector.py](PC-Canary/evaluator/core/state_inspector.py)
- [PC-Canary/evaluator/core/hook_manager.py](PC-Canary/evaluator/core/hook_manager.py)

**Changes:** All Chinese log messages, docstrings, and comments translated to English

### Fix 2.5: Support Commands in PATH
**File:** [PC-Canary/evaluator/core/hook_manager.py](PC-Canary/evaluator/core/hook_manager.py)

**Changes:**
- Updated `start_app()` to use `shutil.which()` to resolve commands in PATH
- Previously only checked `os.path.exists()` for absolute paths
- Now supports both absolute paths and commands like `xdg-open`

**Code:**
```python
import shutil
resolved_path = self.app_path if os.path.exists(self.app_path) else shutil.which(self.app_path)
```

### Fix 3: Handler Implementation
**File:** [PC-Canary/tests/tasks/obsidian/task01_createNote/handler.py](PC-Canary/tests/tasks/obsidian/task01_createNote/handler.py)

**Changes:**
- Simplified from async MCP client to direct filesystem check
- Uses `os.path.exists()` to verify note creation
- Added `message_handler()` to prevent BaseEvaluator warnings
- Properly implements StateInspector pattern with `inspector_on_start()` and `inspector_on_completion()`

### Fix 4: Obsidian Launch Method
**File:** [PC-Canary/tests/tasks/obsidian/task01_createNote/config.json](PC-Canary/tests/tasks/obsidian/task01_createNote/config.json)

**Initial attempt:**
- Tried using `xdg-open` with `obsidian://` URI protocol
- Failed with "Operation not supported" - URI handler not registered in container

**Final solution:**
- `executable_path`: `"/usr/local/bin/obsidian"` (direct wrapper path)
- `args`: `[]` (no arguments needed - Obsidian opens last vault by default)

**Reason:** Direct execution is simpler and more reliable than URI protocol in containerized environment

---

## Verification Results (2025-12-01)

**Obsidian Installation:**
- Location: `/home/agent/squashfs-root/` inside MCPWorld container
- Wrapper script: `/usr/local/bin/obsidian` (properly configured with absolute path)
- Binary verified: `/home/agent/squashfs-root/obsidian` exists

**Launch Method:**
- Using direct wrapper execution: `/usr/local/bin/obsidian`
- No URI protocol needed (xdg-open approach failed in container)
- Obsidian opens last vault by default

**Current Configuration Status:**
- ✅ Obsidian installed and extracted
- ✅ Wrapper script created with correct absolute path
- ✅ hook_manager.py supports PATH commands
- ✅ config.json uses direct wrapper execution
- ✅ Task timeout increased to 500 seconds
- ✅ Instruction template optimized for faster completion
- ⏳ Ready for task execution testing

**Performance Notes:**
- Task typically completes in 2-3 steps (create + optional verification)
- Instruction template allows one verification check using `obsidian_list_files_in_vault`
- Recommended settings for fastest execution:
  - `--exec_mode api` - Skip screenshot processing (Obsidian uses MCP tools only)
  - `--max_steps 3` - Allow create + verify + response
- Mixed mode is slower due to vision model processing screenshots on each turn
- Example commands:
  ```bash
  # Fast (API-only mode, no screenshots)
  python computer-use-demo/run_pure_computer_use_with_eval.py \
    --provider openai \
    --openai_api_key dummy \
    --openai_base_url $OPENAI_BASE_URL \
    --openai_endpoint /v1/chat/completions \
    --model qwen3-vl:32b \
    --task_id obsidian/task01_createNote \
    --log_dir logs_computer_use_eval \
    --exec_mode api \
    --max_steps 3

  # Standard (mixed mode with screenshots)
  python computer-use-demo/run_pure_computer_use_with_eval.py \
    --provider openai \
    --openai_api_key dummy \
    --openai_base_url $OPENAI_BASE_URL \
    --openai_endpoint /v1/chat/completions \
    --model qwen3-vl:32b \
    --task_id obsidian/task01_createNote \
    --log_dir logs_computer_use_eval \
    --exec_mode mixed \
    --max_steps 3
  ```

---

## 5. Additional Tasks (task02–task06)

**Date:** 2025-12-01

We expanded the Obsidian benchmark suite with five additional tasks, each mirroring VS Code-style scenarios.

### Context Data Updates
- Added `Archive/`, `Projects/`, and `Daily/` folders under `tests/context_data/obsidian/sample-vault/`.
- Seeded the vault with scenario-specific notes: `Archive/ArchiveMe.md`, `Projects/ProjectPlan.md`, `MeetingNotes.md`, and `Ideas.md`.
- These files are restored via the `context_data` entries in every task to guarantee deterministic starting points.

### New Tasks
1. **task02_deleteNote** – Remove `Archive/ArchiveMe.md`. Success when the file no longer exists anywhere in the vault.
2. **task03_appendToNote** – Append a summary block to `Projects/ProjectPlan.md`, verified by checking the file ends with `append_text`.
3. **task04_renameNote** – Rename `MeetingNotes.md` to `ClientMeeting.md` and confirm the source file disappears while the target retains the expected content snippet.
4. **task05_createDailyNote** – Create `Daily/Daily-2025-01-01.md` with a checklist template (exact content match required).
5. **task06_moveNote** – Move `Ideas.md` into `Archive/Ideas.md`, validating both absence at the original path and presence with matching content in the destination.

Shared characteristics:
- Each task registers `handler.py` as both hook and handler so the StateInspector trigger runs when the agent exits (e.g., user types `quit`).
- Handlers emulate the updated pattern from task01: `inspector_on_completion` emits a simple event, and `message_handler` performs filesystem verification.
- MCP server configuration and tool usage remain identical to task01 to ensure consistent agent capabilities.

---

## 6. Batch Runner Script

**Date:** 2025-12-01

- Added `scripts/run_tasks_range.sh`, a unified helper for running either VS Code or Obsidian task ranges.
- Usage: `./scripts/run_tasks_range.sh <suite> <start> <end> [log_root]`, where `suite` is `vscode` or `obsidian`.
- If `log_root` is omitted, logs land in `logs_computer_use_eval/vscode_runs` or `logs_computer_use_eval/obsidian_runs` automatically, keeping suites isolated.
- Example command (runs the first ten Obsidian tasks and stores output under `logs/batch_obsidian`):

  ```bash
  ./scripts/run_tasks_range.sh obsidian 1 10 logs/batch_obsidian
  ```

- CSV summaries/metrics share the same prefix as the suite (e.g., `obsidian_batch_summary.csv`, `obsidian_metrics.csv`) to make downstream comparisons easier.

---

**Last Updated:** 2025-12-01
