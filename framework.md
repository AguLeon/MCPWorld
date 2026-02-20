# Framework

This document summarizes the evaluation framework used in this repository. The framework executes MCP-enabled computer-use agents in a controlled environment and produces deterministic task-level results, traces, and resource metrics. The architecture is: ![Architecture](./docs/architecture.png)

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Components](#components)
  - [Containerized environment](#containerized-environment)
  - [Agent client](#agent-client)
  - [Tasks and context](#tasks-and-context)
  - [Evaluation and tracing](#evaluation-and-tracing)
  - [Application and model support](#application-and-model-support)
- [Overview of the system](#overview-of-the-system)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

---

## Components

### Containerized environment
The framework uses two containerized runtimes:

1. **Application environment**: an Ubuntu-based container that hosts the target applications and exposes a virtual desktop interface. Containerization provides a uniform execution surface across host machines and reduces variability from local software installations.

2. **Model backend**: a model server exposed through an OpenAI-compatible API. In our experiments we use Ollama, but other OpenAI-compatible servers can be used.

When models are self-hosted, the framework can collect hardware telemetry during execution. For GPU runs, it polls utilization, memory use, temperature, and power and stores a time series for post-hoc analysis. The evaluator aggregates these samples into task-level resource and energy metrics.

### Agent client
The agent executes tasks using a Plan-Act-Observe loop (`loop.py`). At each step, it builds a prompt from the task specification and current observations, queries the model backend, and executes the returned actions.

The action space supports three modalities:
- GUI actions on the virtual desktop
- Shell command execution inside the environment
- MCP tool calls when an application exposes an MCP server

This mixed-modality design supports applications with and without programmatic interfaces.

### Tasks and context
Each benchmark task consists of:
- **Task specification** (`config.json`): the natural language instruction, variable substitution fields, timeout limits, and key steps for progress tracking
- **Evaluation logic** (`handler.py`): deterministic checks for task completion using application state, filesystem artifacts, and emitted events
- **Context data**: the initial workspace state (for example, project files and application configuration)

Before each run, the evaluator restores context into a fresh working directory to ensure isolation and reproducibility.

### Evaluation and tracing
The evaluator records an execution trace for every run. The trace includes model request and response timestamps, tool invocations with arguments and return values, and environment observations (for example, screenshots and command outputs). For applications that support internal instrumentation, the framework also collects application events emitted from within the runtime (for example, file operations or configuration changes). These events provide a white-box signal for progress and completion.

After execution completes or times out, the evaluator validates task success and aggregates metrics into structured logs. Metrics include success and key-step completion, end-to-end latency, time to first token, number of model calls, tool usage statistics, token counts, and resource measurements from the telemetry stream. The evaluator also flags common failure modes such as repeated action patterns without new progress events and invalid tool invocations.

### Application and model support
The framework supports GUI-only applications and applications with MCP interfaces. When an MCP server is available, agents can use API calls for stateful operations and reserve GUI interaction for actions that lack tool support.

Model backends are configured through `scripts/config.cfg`, which enables controlled comparisons across model families and serving stacks. Screen resolution is treated as an experimental parameter because it can affect coordinate prediction accuracy in GUI actions, especially for vision-language models.

## Overview of the system
![Overview](docs/mcpworld_system.png)

**For Depth Description**: Please look up the [onboarding application guide](./onboard-application.md)
