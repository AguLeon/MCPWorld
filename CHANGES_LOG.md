# Changes Log - Qwen Vision Model Integration Session

## Date: 2025-11-17

### Session Goal
Fix issues with Qwen vision model (qwen3-vl:32b) running MCPWorld benchmarking tasks, specifically:
1. Clean up verbose logging
2. Fix "Original file snapshot unavailable" error in task02
3. Improve task completion verification and explanatory text for Qwen

---

## Changes Made

### 1. **Logging Cleanup - ipc_injector.py**
**File:** `/home/cc/MCPWorld/PC-Canary/evaluator/core/ipc_injector.py`

**Changed:** Reduced verbose logging from 5-6 messages per event to 1-2 concise messages

**Key changes:**
- Line 64: Combined multiple log messages into one: `_safe_log("info", f"Client {sid} connected, injected {len(scripts_snapshot)} script(s)")`
- Line 82: Condensed message logging: `_safe_log("info", f"App → evaluator: {message.get('event_type', 'unknown')}")`
- Line 93, 96: Condensed queue processing logs

**Reverse:** Restore original verbose logging with separate messages for each action

---

### 2. **Logging Cleanup - code.sh**
**File:** `/home/cc/MCPWorld/PC-Canary/apps/vscode/scripts/code.sh`

**Changed:** Removed all DEBUG echo statements except one, added stderr filtering for Chromium errors

**Kept only:**
- Line 22: `echo "[DEBUG] code() function called with args: $@" >&2`

**Removed DEBUG statements:**
- `[DEBUG] Script started`
- `[DEBUG] After nvm sourcing`
- `[DEBUG] After set -e`
- `[DEBUG] Checking environment...`
- `[DEBUG] Docker branch - calling code function`
- `[DEBUG] Changed to ROOT`
- `[DEBUG] Electron binary path`
- `[DEBUG] About to exec`
- `[DEBUG] WSL/WSLG/Default branch`
- `[DEBUG] After code call, exit code`

**Added stderr filtering (Line 63):**
```bash
exec "$CODE" . $DISABLE_TEST_EXTENSION "$@" 2> >(grep -v -E '(ERROR:bus\.cc|ERROR:object_proxy\.cc|INFO:CONSOLE|WARNING:bluez_dbus_manager|WARNING:power_observer_linux|WARNING:viz_main_impl\.cc|WARNING:gpu_memory_buffer_support|WARNING:sandbox_linux\.cc|ERROR:viz_main_impl\.cc|Failed to connect to the bus)' >&2)
```

**Reverse:** Remove stderr filtering, restore all DEBUG echo statements

---

### 3. **Key Parameter Fix - collection.py**
**File:** `/home/cc/MCPWorld/computer-use-demo/computer_use_demo/tools/collection.py`

**Changed:** Added normalization for models that send `key` parameter instead of `text` for key actions

**Added (Lines 88-91):**
```python
# Handle action="key" with key parameter instead of text
# Some models send {"action": "key", "key": "Ctrl+h"} when they should send {"action": "key", "text": "Ctrl+h"}
if act == "key" and "key" in tool_input and "text" not in tool_input:
    tool_input["text"] = tool_input.pop("key")
```

**Why:** Qwen was sending `{"action": "key", "key": "Ctrl+h"}` which caused error "text is required for key"

**Reverse:** Remove lines 88-91

---

### 4. **Logging Cleanup - loop.py**
**File:** `/home/cc/MCPWorld/computer-use-demo/computer_use_demo/loop.py`

**Changed:** Removed less useful DEBUG messages

**Removed:**
- MCP server connection messages (lines 270, 272, 276-279)
- "assistant returned no tool calls; exiting loop" message (line 423)
- cleanup enter/complete messages (lines 471, 475)

**Kept:**
- `[DEBUG] sampling_loop: invoking provider {provider} model={model} messages={len}`
- `[DEBUG] sampling_loop: provider response received`

**Reverse:** Restore all removed DEBUG print statements

---

### 5. **Initial Screenshot + Generic Note - run_pure_computer_use_with_eval.py**
**File:** `/home/cc/MCPWorld/computer-use-demo/run_pure_computer_use_with_eval.py`

**Changed:** Added initial screenshot and generic note on first turn to prevent opening duplicate applications

**Added (Lines 202-228):**
```python
# Add user input to message history
# On first turn, add generic context about pre-opened applications
user_message_text = user_input
if turn_count == 0:
    user_message_text = f"{user_input}\n\nNote: The application is already open on the desktop. Do not open it again - work with the existing instance."

messages.append({
    "role": "user",
    "content": [{"type": "text", "text": user_message_text}]
})

# Add initial screenshot on first turn to show agent current desktop state
if turn_count == 0 and "computer" in tool_collection.tool_map:
    computer_tool = tool_collection.tool_map["computer"]
    try:
        initial_screenshot = await computer_tool.screenshot()
        if initial_screenshot.base64_image:
            messages[-1]["content"].append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": initial_screenshot.base64_image
                }
            })
            print("[Initial screenshot attached to show current desktop state]")
    except Exception as e:
        print(f"[Warning: Failed to capture initial screenshot: {e}]")
```

**Why:** Generic solution (not app-specific) to prevent agent from opening duplicate applications

**Reverse:** Remove the first-turn special handling for screenshot and note

---

### 6. **Socket Timing Fix - hooker.js** ⚠️ LATEST CHANGE
**File:** `/home/cc/MCPWorld/PC-Canary/tests/tasks/vscode/task02_wordReplaceInFile/hooker.js`

**Changed:** Replaced immediate send + connect listener with setTimeout delay

**Original (BEFORE - what we replaced):**
```javascript
readFile("/workspace/.mcpworld/vscode/C-Plus-Plus/bubble_sort.cpp").then(origin_file_content => {
    socket.emit("send", {
        event_type: "read_origin_content",
        message: "Captured original file contents at task start",
        content: origin_file_content
    });
});
```

**Current (AFTER - lines 23-33):**
```javascript
// Send initial file content after a brief delay to ensure socket is fully connected
// The script is injected during the connect event, so we need to wait for that to complete
setTimeout(() => {
    readFile("/workspace/.mcpworld/vscode/C-Plus-Plus/bubble_sort.cpp").then(origin_file_content => {
        socket.emit("send", {
            event_type: "read_origin_content",
            message: "Captured original file contents at task start",
            content: origin_file_content
        });
    });
}, 100);
```

**Why:**
- Hooker is injected DURING the socket connect event
- Listening for `socket.on('connect')` is too late - event already fired
- Immediate emit happens inside connect handler before completion
- 100ms delay ensures connection is fully established

**Reverse:** Replace setTimeout with original immediate readFile().then() pattern

---

### 7. **Enhanced System Prompts for Task Completion - loop.py** ⚠️ NEW
**File:** `/home/cc/MCPWorld/computer-use-demo/computer_use_demo/loop.py`

**Changed:** Added task completion guidelines to system prompts to improve Qwen's behavior

**Added (Lines 156-164):**
```python
# Additional guidelines for ensuring proper task completion and verification
TASK_COMPLETION_GUIDELINES = """
<TASK_COMPLETION>
* After completing what you believe to be the final step of the task, ALWAYS take a screenshot to verify the result.
* Describe what you see in the verification screenshot and explicitly state whether the task has been completed successfully.
* If the task involved editing a file, verify it was saved (check for the unsaved indicator in the editor).
* If the task involved multiple steps, briefly summarize what was accomplished.
* End your response with a clear statement: "Task completed successfully" or "Task requires additional steps: [explanation]".
</TASK_COMPLETION>"""
```

**Modified (Lines 294-300):**
```python
# Always append task completion guidelines for better verification behavior
system_prompt_with_completion = f"{base_system_prompt}\n{TASK_COMPLETION_GUIDELINES}"
system_prompt_text = (
    f"{system_prompt_with_completion} {system_prompt_suffix}"
    if system_prompt_suffix
    else system_prompt_with_completion
)
```

**Why:**
- Qwen was not providing explanatory text before tool calls
- Agent was stopping without verifying task completion
- No final summary of what was accomplished
- The enhanced prompts explicitly instruct the model to:
  1. Take verification screenshots
  2. Describe what it sees
  3. Provide completion status
  4. Summarize actions taken

**Reverse:**
1. Remove TASK_COMPLETION_GUIDELINES definition (lines 156-164)
2. Restore original system_prompt_text assignment (lines 294-300):
```python
system_prompt_text = (
    f"{base_system_prompt} {system_prompt_suffix}"
    if system_prompt_suffix
    else base_system_prompt
)
```

---

## Summary of Intent

### Problem 1: Verbose Logging ✅ SOLVED
- **Issue:** Too many debug messages cluttering output
- **Solution:** Reduced to essential messages only
- **Files affected:** ipc_injector.py, code.sh, loop.py

### Problem 2: Key Parameter Mismatch ✅ SOLVED
- **Issue:** Qwen sends `{"action": "key", "key": "Ctrl+h"}` instead of `{"action": "key", "text": "Ctrl+h"}`
- **Solution:** Added normalization in collection.py
- **Files affected:** collection.py

### Problem 3: Duplicate VSCode Instances ✅ SOLVED
- **Issue:** Agent tries to open VSCode when it's already running
- **Solution:** Add initial screenshot + generic note on first turn
- **Files affected:** run_pure_computer_use_with_eval.py

### Problem 4: Original File Snapshot Unavailable ⚠️ IN TESTING
- **Issue:** Evaluator never receives `read_origin_content` event
- **Root cause:** Hooker injected during connect event, timing issue prevents message from being received
- **Solution:** Use setTimeout(100ms) to delay send until connection fully established
- **Files affected:** hooker.js

### Problem 5: Agent Not Providing Explanations or Verification ⚠️ NEW
- **Issue:**
  - Qwen not providing explanatory text before tool calls
  - Agent stopping without verifying task completion
  - No final summary or completion status
  - User doesn't know if task succeeded
- **Root cause:** Qwen doesn't follow system prompt instructions as strictly as Claude
- **Solution:** Add explicit TASK_COMPLETION_GUIDELINES to system prompts instructing model to:
  - Take verification screenshots after final step
  - Describe what it sees in screenshots
  - Provide completion status
  - Summarize actions taken
- **Files affected:** loop.py

---

## How to Reverse All Changes

### Quick Reverse (per file):

1. **ipc_injector.py** - Check git diff and restore original verbose logging
2. **code.sh** - Restore all DEBUG echo statements, remove stderr filtering
3. **collection.py** - Remove lines 88-91 (key→text normalization)
4. **loop.py** - Restore removed DEBUG prints + remove TASK_COMPLETION_GUIDELINES (lines 156-164 and 294-300)
5. **run_pure_computer_use_with_eval.py** - Remove first-turn screenshot/note logic
6. **hooker.js** - Replace setTimeout with original immediate emit

### 10. **VSCode Context Data Alignment (Tasks 04–25)**
**Directories/files:** `tests/context_data/vscode/...`

**Changes:** Ensured every VSCode task points to actual context data and added missing files:
- Created `C-Plus-Plus/.vscode/settings.json`, `data_structures/`, `sorting/bubble_sort{,.cpp}`, `ciphers/uint256_t.hpp`, `agent_test/{debug_until.cpp, fix_error.cpp, change_name.cpp}`, `operations_on_datastructures/get_size_of_linked_list.cpp`, and `python_test/sort_import.py`.
- Added minimal `.vscode/` and `extensions/` scaffolding so configs copying `/workspace/.mcpworld/vscode/.vscode/` resolve.
- Updated all VSCode `config.json` files to copy `tests/context_data/vscode/user_data` into `/workspace/.mcpworld/vscode/user_data` (instead of the old `vscode_user_data_dir`).

**Reverse:** Remove the new context files/folders and revert the config `context_data` entries to the previous paths.

### 11. **Batch Runner & Metrics Aggregator**
**Files:** `scripts/run_vscode_range.sh`, `scripts/collect_metrics.py`, `logs_computer_use_eval/vscode_metrics.csv`

**Changes:**
- Added `scripts/run_vscode_range.sh` to run a range of VSCode tasks sequentially, piping default instructions automatically and appending to `logs_computer_use_eval/vscode_batch_summary.csv`.
- Added `scripts/collect_metrics.py` which parses each task's `result_*.json` and records status, reason, duration, tool/error counts, etc., into `logs_computer_use_eval/vscode_metrics.csv`.
- The range runner now truncates summary/metrics files at startup and invokes the collector after each task.

**Reverse:** Delete the scripts, remove `vscode_metrics.csv`, and revert `scripts/run_vscode_range.sh` to its pre-batch state (or delete it entirely).

### Git Commands:
```bash
# Check what changed
git diff PC-Canary/evaluator/core/ipc_injector.py
git diff PC-Canary/apps/vscode/scripts/code.sh
git diff computer-use-demo/computer_use_demo/tools/collection.py
git diff computer-use-demo/computer_use_demo/loop.py
git diff computer-use-demo/run_pure_computer_use_with_eval.py
git diff PC-Canary/tests/tasks/vscode/task02_wordReplaceInFile/hooker.js

# Reverse specific file
git checkout HEAD -- <file_path>

# Or reverse all changes
git reset --hard HEAD
```

---

## Testing Status

- ✅ Logging cleanup - WORKING
- ✅ Key parameter fix - WORKING (Ctrl+H works now)
- ✅ Initial screenshot/note - IMPLEMENTED (generic approach)
- ⚠️ Socket timing fix - NEEDS TESTING
- ⚠️ Enhanced task completion prompts - NEEDS TESTING

**Next steps:**
1. Run task02 to verify the setTimeout fix resolves "Original file snapshot unavailable" error
2. Run task02 again to verify enhanced prompts improve Qwen's explanatory text and task verification behavior
3. Expected improvements:
   - Agent provides explanations before each tool call
   - Agent takes verification screenshot after completing task
   - Agent explicitly states "Task completed successfully" or explains what's left
   - Better visibility into agent's thinking and actions
