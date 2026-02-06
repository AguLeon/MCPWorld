# Framework

This section describes the MCPWorld evaluation framework architecture, consisting of two containerized environments, an agent client, task definitions, and an evaluation pipeline.

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Architecture](#architecture)
- [1. Environment](#1-environment)
  - [1.1 Applications and Virtual Desktop](#11-applications-and-virtual-desktop)
  - [1.2 LLM Container](#12-llm-container)
- [2. Framework Components](#2-framework-components)
  - [2.1 Client](#21-client)
  - [2.2 Tasks](#22-tasks)
  - [2.3 Evaluator](#23-evaluator)
  - [2.4 End-to-End Execution](#24-end-to-end-execution)
- [3. LLM Support](#3-llm-support)
- [4. Application Support](#4-application-support)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->


---
### Architecture
![Architecture](/docs/architecture.png)

---

### 1. Environment

#### 1.1 Applications and Virtual Desktop

The MCPWorld container provides the primary execution environment, running Ubuntu 22.04 with all target applications installed (VSCode, Obsidian, Telegram, FreeTube, etc.). A virtual desktop is served via TurboVNC on port 5904 and exposed through noVNC on port 6080 for browser-based access. This containerized approach ensures consistent, reproducible evaluation conditions across different host systems and eliminates variability from local software configurations or operating system differences.

#### 1.2 LLM Container

A dedicated Ollama container serves locally-hosted language models through an OpenAI-compatible API on port 11434. Self-hosting provides two key advantages: full control over the inference environment and access to fine-grained resource metrics. The host monitors GPU utilization, VRAM consumption, temperature, and power draw via nvidia-smi polling throughout each task, logging measurements to CSV files for post-hoc analysis. These metrics—unavailable when using external APIs—enable cost estimation, bottleneck identification, and energy consumption comparisons across model configurations.

---

### 2. Framework Components

#### 2.1 Client

The agent client orchestrates task execution through a Plan-Act-Observe loop implemented in `loop.py`. It connects to the Ollama container via HTTP requests to the OpenAI-compatible endpoint (`http://host.docker.internal:11434/v1/chat/completions`), sending prompts constructed from task definitions and receiving structured tool calls in response.

For GUI interactions, the client executes actions in the virtual desktop using xdotool for mouse and keyboard control, capturing screenshots as visual observations. The available tools span three modalities: GUI operations (click, type, screenshot), shell commands (bash execution), and MCP API calls when applications expose them.

**Trace Production.** The evaluator instruments every agent action by recording LLM query timestamps, tool invocations, arguments, and results. For applications supporting internal state inspection—such as VSCode via Socket.IO—`hooker.js` scripts inject into the application runtime to emit real-time events (e.g., file saved, theme changed, extension installed). These events, combined with filesystem state changes monitored by the evaluator, form comprehensive action traces used for evaluation.

#### 2.2 Tasks

A task defines a single benchmark instance requiring three components:

- **Task Definition** (`config.json`): Specifies the instruction prompt (with variable substitution), expected key steps for progress tracking, timeout limits, ground truth labels, and evaluation parameters.
- **Evaluation Logic** (`handler.py`): Contains validation functions that check whether the agent achieved the intended outcome by inspecting application state, file contents, or emitted events.
- **Context Data**: Initial files, application configuration, and state (e.g., vault contents for Obsidian, workspace settings for VSCode) that simulate realistic usage scenarios.

Context data is copied to a working directory before each run via rsync, preserving original files for reproducibility. This isolation ensures the evaluator can detect modifications made by the agent while maintaining a clean baseline for subsequent runs.

#### 2.3 Evaluator

The evaluation pipeline operates in four stages:

1. **Setup**: Context data is restored to ensure a clean initial state; target applications are launched.
2. **Monitoring**: During execution, the evaluator collects events from hook scripts, monitors filesystem changes, and records all tool calls.
3. **Validation**: Upon task completion or timeout, `handler.py` executes validation logic, checking key-step completion and comparing outcomes against ground truth.
4. **Aggregation**: Results are compiled into JSON logs containing raw events and computed metrics.

**Computed Metrics.** The evaluator extracts metrics from traces including: task duration, time to first token, LLM call count, tool usage statistics (success/failure rates per tool type), key-step completion ratio, and token consumption. Quality indicators detect failure modes—loop detection identifies repeated actions without progress, and hallucination detection flags calls to non-existent tools or malformed parameters.

#### 2.4 End-to-End Execution

A complete evaluation run proceeds through four phases:

1. **Environment Initialization**: Containers start; models are loaded into GPU memory via Ollama.
2. **Task Setup**: The evaluator restores context data and launches target applications in the virtual desktop.
3. **Agent Execution**: The client runs the Plan-Act-Observe loop, sending observations to the LLM and executing returned tool calls until the task completes, times out, or encounters an unrecoverable error.
4. **Result Collection**: The evaluator computes final metrics, generates reports, and saves JSON logs for analysis.

---

### 3. LLM Support

The framework supports three provider categories: self-hosted models via Ollama (enabling detailed resource monitoring), Anthropic models via external API, and any OpenAI-compatible endpoint (vLLM, LM Studio, etc.).

**Supported Model Families.** Vision-language models enabling GUI interaction include Qwen3-VL (2B to 235B parameters), Gemma3-tools, Llama4, Ministral, and Devstral. Claude models (3.5/3.7 Sonnet) are supported via Anthropic API or cloud providers (Bedrock, Vertex).

**Resolution Sensitivity.** Screen resolution significantly affects model performance. Qwen family models require square resolutions (e.g., 1000×1000) for accurate coordinate prediction in GUI tasks, while Claude performs optimally with rectangular resolutions (e.g., 1024×768). Models are configured via `models.cfg`; adding new Ollama-compatible models requires only appending entries to this file.

---

### 4. Application Support

MCPWorld accommodates both GUI and CLI applications through combined access to the virtual desktop (screenshots, mouse, keyboard) and bash shell (command execution). This dual-modality support enables agents to fall back to GUI interaction when programmatic interfaces are unavailable.

**MCP vs. Non-MCP Applications.** Applications with MCP server implementations (e.g., Obsidian via `mcp-obsidian`, VSCode via Socket.IO extension) enable API-based interactions alongside GUI control, allowing agents to choose the most efficient modality. Non-MCP applications rely solely on computer-use tools. The framework includes an MCP proxy for simulating protocol-compliant interactions during development.

**Onboarding New Applications.** Adding applications requires three steps: (1) ensuring the application is discoverable via PATH or symbolic links (with `--no-sandbox` flags for Electron apps running in Docker); (2) creating task definitions with `config.json` specifying prompts, key steps, and context data locations; and (3) implementing `handler.py` with validation logic that checks task outcomes against expected results.

**For Depth Description**: Please look up the [onboarding application guide](./onboard-application.md)
