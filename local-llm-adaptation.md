# Local LLM Adaptation Log

## Purpose
- Track design decisions and code changes that enable non-Anthropic providers (OpenAI-compatible local models).
- Record follow-up tasks, testing notes, and outstanding risks as the refactor progresses.

## Key Objectives
- Decouple Anthropic-specific assumptions in the sampling loop and tool layer.
- Support interchangeable OpenAI-style endpoints (e.g., Ollama, vLLM, HF TGI).
- Preserve evaluator instrumentation, Streamlit UX, and headless workflows.

## Task Tracker
- [x] Create adaptation log and initialise objectives.
- [x] Catalogue Anthropic-only touchpoints (loop, tools, MCP bridge, UI, scripts, tests).
- [x] Define provider-neutral request/response data structures.
- [x] Implement provider abstraction layer with Anthropic adapter; plan OpenAI path.
- [x] Normalise tool serialization across providers (core tools + MCP specs).
- [x] Extend Streamlit/headless entry points for provider selection and config.
- [x] Add optional Ollama orchestration and model management utilities.
- [x] Document RAM-backed Ollama workflow for oversized local models.
- [ ] Expand automated and manual test coverage for new providers.
- [x] Fix bootstrap API_PROVIDER casing (lowercase) to align with Streamlit expectations.

## Notes
- Keep this document updated after each substantive change (commit, configuration update, or design decision).
- Capture any schema or protocol nuances that differ between providers for future maintainers.

### Baseline Anthropic Dependencies (2025-03-18)
- `computer_use_demo/loop.py`: hard-coded Anthropic SDK clients (`Anthropic`, `AnthropicBedrock`, `AnthropicVertex`) and beta message/tool types.
- `computer_use_demo/tools/`: tool classes import `anthropic.types.beta` definitions; serialization assumes Anthropic schemas.
- `computer_use_demo/streamlit.py`: provider list limited to Anthropic family; reads/writes `~/.anthropic` credentials and handles Anthropic-specific errors.
- Headless runners (`run_pure_computer_use.py`, `run_pure_computer_use_with_eval.py`) directly depend on Anthropic SDK types.
- MCP bridge (`computer_use_demo/mcpclient.py`) returns `BetaToolParam` objects from Anthropic types.
- Tests import Anthropic beta message/tool classes (`computer_use_demo/tests/`).
- Requirements pin `anthropic[bedrock,vertex]`; README content references Anthropic-only setup paths.
- PC-Canary `agent/models/claude_model.py` provides a Claude-specific model adapter that may require analogous treatment once multi-provider support lands.

## Design Notes

### Provider-Neutral Conversation Model (2025-03-18)
- Introduce `ConversationMessage` dataclass (`role`, `segments`, `metadata`) where `segments` is a list of `MessageSegment` variants.
- `MessageSegment` variants:
  - `TextSegment` (`type="text"`, `text`, optional `annotations`).
  - `ThinkingSegment` (`type="thinking"`, `content`, optional `signature`).
  - `ToolCallSegment` (`type="tool_call"`, `tool_name`, `arguments`, `call_id`).
  - `ToolResultSegment` (`type="tool_result"`, `call_id`, `output_text`, `images`, `is_error`, optional `system_note`).
- Maintain existing `ToolResult` object but align fields with `ToolResultSegment` for round-tripping.
- `ConversationTranscript` helper wraps message list plus system prompt(s) to simplify adapter inputs.

### Tool Specification Abstraction
- Define `ToolSpec` dataclass (`name`, `description`, `input_schema`, `tool_type`, optional execution hints).
- `ToolSpecSerializer` handles conversion into provider payloads (Anthropic beta tool schema vs. OpenAI `function`/`tool` objects).
- Extend MCP client to output `ToolSpec` instead of Anthropic Beta types.
- `ToolCollection` updated to expose `specs()` returning `list[ToolSpec]` and runtime map keyed by `name`.

### Provider Adapter Interface
- New `BaseProviderAdapter` protocol/class with:
  - `provider_id: str`.
  - `prepare_request(transcript: ConversationTranscript, tools: list[ToolSpec], options: ProviderOptions) -> ProviderRequest`.
  - `async invoke(request: ProviderRequest) -> ProviderResponse`.
  - `parse_response(response: ProviderResponse) -> ConversationMessage`.
  - `supports_thinking`, `supports_image_outputs`, `max_output_tokens` helpers.
- `ProviderOptions` captures model name, token limits, temperature, thinking budget, prompt suffix, etc.
- Implementations:
  - `AnthropicAdapter` mirrors current beta.messages flow (prompt caching, thinking, tool schema).
  - `OpenAIAdapter` targets OpenAI-compatible /v1/chat/completions endpoints (for Ollama, vLLM, HF TGI). Converts tool calls to `function_call` payloads and parses `tool_calls` array into `ToolCallSegment`.

### Integration Touchpoints
- `sampling_loop` refactored to:
  - Build `ConversationTranscript` / `ToolSpec` list.
  - Select adapter via `ProviderRegistry` (mapping provider enum to adapter instance).
  - Feed tool results back by synthesizing `ToolResultSegment` entries.
  - Maintain evaluator hooks and timeout logic around provider-agnostic structures.
- Streamlit/headless scripts:
  - Operate on provider IDs defined by registry.
  - Persist provider-specific connection details (`api_key`, `base_url`) separately.
- Tests:
  - Add adapter contract tests with fixture transcripts.
  - Mock provider responses for unit coverage without SDK dependencies.

### Implementation Progress
- **2025-03-18**: Added `computer_use_demo/providers/` package with provider-agnostic data models (`ConversationMessage`, `ToolSpec`, `ProviderRegistry`, etc.) to support upcoming adapter implementations.
- **2025-03-18**: Implemented `AnthropicAdapter` and registered it via the provider registry; updated `ToolCollection` and `MCPClient` to emit `ToolSpec` metadata.
- **2025-03-18**: Refactored `sampling_loop` to consume the registry/adapter flow, translate messages into provider-neutral segments, and delegate SDK calls through the Anthropic adapter without changing external behaviour.

### Detailed Change Log (2025-03-18)

**Providers Package (`computer_use_demo/providers/`)**
- Added `base.py` with dataclasses for conversation roles, message segments, transcripts, tool specifications, provider options, and a registry for adapters.
- Created `AnthropicAdapter` to wrap existing SDK behaviour; handles request preparation, invocation with raw-response hooks, and conversion back to neutral message segments.
- Implemented `OpenAIAdapter` to target OpenAI-compatible `/v1/chat/completions` APIs (`openai_adapter.py`):
  - `prepare_request`: builds the full URL (`base_url` + `endpoint`), injects system prompts, converts transcripts into OpenAI message arrays, and serialises `ToolSpec` instances into function tool payloads (`tool_choice` defaults to `auto` but can be overridden via `ProviderOptions.extra_options`).
  - Handles optional knobs (`temperature`, `max_tokens`, `response_format`, custom headers, timeouts) and threads `api_response_callback` through the request object for consistent logging.
  - `invoke`: performs asynchronous HTTP POST via `httpx.AsyncClient`, surfaces transport errors through the callback pathway, and raises for non-2xx responses to preserve existing error handling semantics.
  - `parse_response`: walks `choices[0].message`, capturing mixed content, `tool_calls`, and legacy `function_call` fields; it normalises arguments via `json.loads`, falls back to storing raw strings, and attaches the raw payload/finish reason into message metadata for debugging.
  - Helper utilities convert between neutral segments and OpenAI-expected payloads (e.g., `_collect_text_segments`, `_tool_result_to_message`, `_tool_spec_to_openai`) while ignoring unsupported thinking segments for now.
  - Outstanding work: register adapter with the provider registry, surface configuration in Streamlit/headless runners (API key, base URL, timeout), and exercise it against a local server (Ollama/vLLM) once wiring is in place.
- Exported new symbols via package `__init__` for straightforward importing within the rest of the project.
- Follow-up: design an `OpenAIAdapter` that mirrors this API and supports local endpoints.

**Sampling Loop (`computer_use_demo/loop.py`)**
- Introduced `_PROVIDER_REGISTRY` tying Anthropic/BEDROCK/VERTEX providers to their adapter instances.
- Replaced direct SDK calls with adapter lifecycle (`prepare_request` → `invoke` → `parse_response`); registered an OpenAI adapter entry alongside Anthropic/BEDROCK/VERTEX providers (provider enum now includes `"openai"`).
- Added conversion helpers: `_segment_to_beta_block`, `_conversation_message_to_beta`, `_beta_messages_to_transcript`, `_make_tool_result_segment`, `_tool_result_segment_to_beta`.
- Maintains existing evaluator hooks, prompt caching logic, and file logging while using provider-neutral structures internally. `api_response_callback` continues to receive raw HTTP objects for both Anthropic and OpenAI flows.
- Builds both Anthropic-style system blocks and plain string prompts; passes provider-specific options (Anthropic betas/extra_body, OpenAI `base_url`/`endpoint`/`tool_choice`) through `ProviderOptions`. Thinking budget and prompt-caching are preserved for Anthropic, while OpenAI ignores unsupported features.
- Introduced environment knobs (`OPENAI_BASE_URL`, `OPENAI_ENDPOINT`, `OPENAI_TOOL_CHOICE`, `OPENAI_TIMEOUT`, `OPENAI_RESPONSE_FORMAT`) to configure the OpenAI adapter at runtime. Defaults keep remote OpenAI compatibility while permitting local hosts. API key fallback prioritises `api_key` argument but falls back to `OPENAI_API_KEY` if unset.
- Error handling now treats Anthropic SDK failures and `httpx.HTTPError` uniformly, returning the accumulated messages so that the UI can surface failures without crashing the loop.
- Outstanding work: remove lingering dependency on `BetaMessageParam` once OpenAI adapter is added; ensure timeouts propagate through adapters.

**Streamlit UI (`computer_use_demo/streamlit.py`)**
- Added OpenAI provider option to the sidebar, including inputs for API key, base URL, endpoint, tool_choice, timeout, and response_format. Keys persist via `openai_api_key` storage while other fields adopt environment defaults.
- `setup_state` now initialises OpenAI-specific session keys and normalises provider selection; `_resolve_provider_api_key` and `_apply_provider_environment` ensure the correct credentials and environment overrides reach the sampling loop.
- `validate_auth` checks provider-specific prerequisites (Anthropic key, OpenAI key/base URL/endpoint) and the sampling loop call now wraps execution in the environment context so runtime overrides are restored afterwards.

**Headless Scripts (`run_pure_computer_use.py`, `run_pure_computer_use_with_eval.py`)**
- Added `--provider` flag plus OpenAI-compatible options (API key, base URL, endpoint, tool_choice, timeout, response_format) while keeping Anthropic defaults intact.
- Resolved API keys stored on the parsed `args` object and passed into the sampling loop; environment variables are synchronised ahead of execution so the adapter receives consistent configuration.
- Default model auto-switches to `OPENAI_DEFAULT_MODEL`/`gpt-4o` when the provider is OpenAI and the caller leaves the anthropic default unchanged.

**Testing Utilities**
- Added adapter-focused unit tests (`tests/test_openai_adapter.py`) covering request serialization and tool-call parsing.
- Updated `tests/loop_test.py` to exercise `sampling_loop` via the provider registry with stub adapters/tool collections, ensuring tool results and callbacks still flow.
- `python -m pytest` currently blocked in the sandboxed environment (command exits in sandbox); rerun locally or inside project container.

**Current Testing Plan**
- **Anthropic Regression**: run Streamlit UI and both headless scripts with `--provider anthropic` to confirm previous behaviour (tool usage, evaluator logging, prompt caching) remains intact.
- **OpenAI Local Smoke Test**: stand up an OpenAI-compatible server (e.g., vLLM, Ollama) and run Streamlit/headless flows with `--provider openai`, iterating through tool-heavy tasks to validate conversions and tool results. Capture API logs to ensure arguments/IDs align with expectations.
- **Adapter Unit Coverage**: add focused tests for conversation/tool serialization (Anthropic + OpenAI adapters) to guard future changes. Mock HTTP responses for OpenAI adapter to exercise tool_call/response_format parsing.
- **MCP Integration**: run a task that relies on MCP tools (e.g., VS Code) under both providers to confirm MCP-sourced `ToolSpec` objects work in mixed mode.
- **Timeout/Error Handling**: simulate network errors or malformed responses for each provider to verify the loop returns gracefully and Streamlit surfaces errors without crashing.

## Local Provider Runtime Notes
- **vLLM (recommended)**:
  1. Install via `pip install vllm`; download a model (e.g. `TheBloke/Qwen2.5-7B-Instruct-AWQ`).
  2. Launch server: `python -m vllm.entrypoints.openai.api_server --model <model> --dtype auto --port 8000`.
  3. Export `OPENAI_BASE_URL=http://127.0.0.1:8000` (endpoint defaults to `/v1/chat/completions`).
- **Ollama**:
  1. Install Ollama inside container, `ollama pull qwen2.5:7b`.
  2. Start server (`ollama serve`) then set `OPENAI_BASE_URL=http://127.0.0.1:11434` and `OPENAI_ENDPOINT=/v1/chat/completions`.
- **LM Studio / TGI**: any OpenAI-compatible gateway works; ensure CORS disabled for Streamlit usage.
- Expose API to container or host by forwarding ports (6080/8501 already in use—pick non-conflicting port).
- For deterministic testing, keep responses short and disable sampling (`temperature=0` already defaulted).

## Container / Image Considerations
- Base Dockerfile currently tied to Anthropic SDK; ensure `requirements.txt` includes any new dependencies introduced by OpenAI workflows (none required so far).
- If baking OpenAI runtime into the DevContainer, add optional services (vLLM, Ollama) and expose environment variables via `.devcontainer/devcontainer.json`.
- Rebuild image after updating system packages or adding GPU drivers needed by vLLM (CUDA 12.1+ for H100). Use multi-stage build to keep runtime lean.
- Document launch sequence in `WORKSPACE.md` or README so contributors know how to start the OpenAI backend before running tests.

**Tool Metadata (`computer_use_demo/tools/collection.py`)**
- Added `to_specs()` to emit provider-neutral `ToolSpec` instances alongside legacy Anthropic payloads.
- Tagging of tool types (`computer_use`, `bash`, `edit`, `generic`) established for future adapter-specific logic.
- Captured original Anthropic parameters inside `metadata["anthropic_params"]` so adapters can reuse them without additional conversion code.

**MCP Bridge (`computer_use_demo/mcpclient.py`)**
- Modified `list_tools()` to return `ToolSpec` objects with embedded `BetaToolParam` metadata.
- Ensures MCP tools participate in the same adapter workflow as built-in tools.
- No change to `call_tool` execution path; future adapters can rely on neutral results.

**Helper Adjustments**
- Trimmed duplicated Anthropic type imports in the loop; limited usage to only what is required by the adapter.
- Normalised optional typing imports (removed unused `List` alias) to keep the module tidy.
- Left TODO to harmonise prompt caching image truncation across providers (currently Anthropic-specific).

**Documentation**
- Expanded the task tracker to reflect completed design/implementation steps and highlight remaining work (UI/config integration, test expansion).
- Detailed the new modules/functions so future contributors understand why large code additions were necessary.

**Open Questions / Next Actions**
- Harden OpenAI-compatible adapter: add streaming support (optional), surface usage tokens, and improve error handling/retries.
- Expand unit/integration tests for adapters and message conversion; add E2E smoke tests with a stub OpenAI server.
- Document OpenAI-compatible setup paths in README/WORKSPACE; clarify environment variables and defaults.
- Validate provider registry with additional local providers (vLLM/Ollama) before broader rollout.
- Automate tmpfs detection/ownership checks in `bootstrap_env` so large-model workflows set `OLLAMA_HOME` safely without manual remount steps.

## Updates (2025-10-17)
- Implemented OpenAIAdapter (non-streaming) with tool_calls/function_call parsing and provider-neutral segment conversion; integrated into sampling loop and registry.
- Streamlit and headless entry points now support provider selection and OpenAI-compatible configuration (keys, base_url, endpoint, tool_choice, timeout, response_format).
- Fixed bootstrap_env `API_PROVIDER` casing bug (now lowercase) so Streamlit picks up the default provider correctly.
- Confirmed MCP bridge emits provider-neutral `ToolSpec` and interoperates with adapters without further changes.

- Added comprehensive inline comments and docstrings to `tools/bootstrap_env.py` to document sections, functions, and lifecycle, improving maintainability and onboarding.
- Optional Ollama service orchestration added to `tools/bootstrap_env.py` (`--enable-ollama`, host/port overrides) with readiness checks and automatic Streamlit wiring.
- New `tools/manage_ollama_model.py` CLI helps pull/swap Ollama models, stop/evict previous ones, and optionally prune unused layers.
- OpenAI adapter now forwards tool screenshot images as `input_image` blocks so OpenAI-compatible VL models (e.g., Qwen2.5-VL via Ollama) receive base64 screenshots.
- Extended OpenAI adapter unit tests to cover screenshot serialization (pytest is not available locally, so the suite was not executed here).
- Added `pytest` to `computer_use_demo/requirements.txt` so freshly built containers include the test runner by default.
- Added `httpx` to the shared requirements to ensure the OpenAI adapter tests (and runtime HTTP calls) have the dependency available in new containers.
- Added `pytest-asyncio` so async adapter tests run without extra manual setup.
- `tools/bootstrap_env.py` now prepares Ollama automatically (no `--addr` dependency) and can invoke `manage_ollama_model.py` to pull the requested model (`--ollama-model`, `--ollama-keep-others`, `--ollama-no-prune`).
- Improved bootstrap UX: before service startup we now print clear hints (VNC password prompt, service URLs/ports, Streamlit readiness guidance) so users see what the silent prompts mean and where to connect.
- Streamlit is launched with `STREAMLIT_SERVER_HEADLESS=true` and telemetry disabled so the bootstrapper never blocks on the first-run email prompt.
- Streamlit model picker now accepts `default`/blank values; the resolved provider default is applied automatically so users don’t have to retype the model name for single-model deployments.

Known gaps after this update:
- No streaming path in OpenAI adapter yet; usage metrics not surfaced in UI.
- Tests need broader coverage for OpenAI adapter error cases and E2E loop with tools. Need to rerun pytest once dependencies are installed.

## Debug Log (2025-10-20)
- Diagnosed Ollama failing with `permission denied` on `/home/agent/.ollama/id_ed25519` when the model cache was pointed at a host-mounted tmpfs. Root ownership on the mount prevented the `agent` user from writing keys.
- Fix: remount tmpfs on the host with matching UID/GID, then recreate the container symlink so `ollama serve` writes directly into RAM.
- Host setup:
  ```bash
  sudo umount /home/cc/MCPWorld/.ollama_ram  # ignore errors if not mounted
  sudo rm -rf /home/cc/MCPWorld/.ollama_ram
  mkdir -p /home/cc/MCPWorld/.ollama_ram
  sudo mount -t tmpfs -o size=220G,uid=1000,gid=1000 tmpfs /home/cc/MCPWorld/.ollama_ram
  ls -ld /home/cc/MCPWorld/.ollama_ram
  ```
- Container setup (after `docker exec -it mcpworld-aguleon /bin/bash`):
  ```bash
  ls -ld /workspace/.ollama_ram
  rm -rf /home/agent/.ollama
  ln -s /workspace/.ollama_ram /home/agent/.ollama
  export OLLAMA_HOME=/workspace/.ollama_ram
  export OLLAMA_HOST=0.0.0.0
  export OLLAMA_PORT=11434
  ollama serve
  ```
- Verified resolution once `ls -ld /workspace/.ollama_ram` reported `agent` ownership; subsequent pulls land entirely in tmpfs without touching the 40 GB disk.

## Llama 4 Validation Checklist (2025-10-20)
- **Host prep**
  ```bash
  df -h /home/cc/MCPWorld/.ollama_ram
  ```
  Ensure the tmpfs still reports ~220G free before launching a session.
- **Container prep**
  ```bash
  export OLLAMA_HOME=/workspace/.ollama_ram
  export OLLAMA_HOST=0.0.0.0
  export OLLAMA_PORT=11434
  ollama serve  # keep running in foreground pane or tmux window
  ```
- **Model load**
  ```bash
  docker exec -it mcpworld-aguleon /bin/bash
  export OLLAMA_HOME=/workspace/.ollama_ram
  python tools/manage_ollama_model.py \
    --model llama4:latest \
    --pull \
    --evict-others \
    --prune \
    --show-status
  ```
  Confirm `ollama list` shows only `llama4:latest` and `df -h /workspace/.ollama_ram` reflects the expected footprint.
- **Streamlit integration**
  ```bash
  python tools/bootstrap_env.py start \
    --enable-ollama \
    --ollama-model llama4:latest \
    --provider openai
  ```
  Verify the UI detects `OPENAI_BASE_URL=http://127.0.0.1:11434` automatically; override via `--openai-base-url` if running remotely.
- **Functional smoke tests**
  - Run a simple tool invocation (`browser_search`) and verify the adapter surfaces `tool_calls` with valid JSON arguments.
  - Upload a screenshot (via built-in tool pipeline) and confirm Llama 4 receives a `type="input_image"` block; ensure the response references the image content.
  - Inspect `streamlit.log` for latency spikes or schema mismatches; log `ComputerUse` events for post-run analysis.
- **Follow-up actions**
  - Record latency/tok usage to compare against Anthropic/Qwen baselines.
  - Capture any deviations in the `/v1/chat/completions` schema; update `OpenAIAdapter` parsing if Llama 4 introduces new fields (e.g., `response_format` metadata).

## VNC / noVNC Bring-up Notes (2025-10-20)
- Initial TurboVNC launches crashed (`gnome-session` trace) which kept port 5904 closed, so noVNC reported “Failed to connect to server”.
- Confirmed Docker host proxy was listening (`sudo lsof -iTCP:5904`), but container `netstat` showed no listener until TurboVNC stayed up.
- Fixes applied:
  - Reset `/tmp/.X11-unix` permissions inside container (`sudo chown root:root /tmp/.X11-unix && sudo chmod 1777 /tmp/.X11-unix`).
  - Replaced TurboVNC `xstartup.turbovnc` with the project’s minimal script:
    ```bash
    sudo tee /opt/TurboVNC/bin/xstartup.turbovnc >/dev/null <<'EOF'
    #!/bin/sh
    xsetroot -solid grey
    xterm -geometry 80x24+10+10 &
    exec sleep infinity
    EOF
    sudo chmod +x /opt/TurboVNC/bin/xstartup.turbovnc
    ```
  - Regenerated the VNC password (`/opt/TurboVNC/bin/vncpasswd`) and relaunched `vncserver :4 -geometry 1280x800 -depth 24`.
  - Verified the listener with `netstat -tuln | grep 5904` inside the container before restarting noVNC (`python tools/bootstrap_env.py stop/start --only novnc`).
- Result: noVNC now connects reliably; current session exposes a basic `xterm` desktop (need to install a full DE later if desired).
