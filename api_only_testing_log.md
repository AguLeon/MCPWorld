# API Only Testing Log

- Session initialized: Created this log to track actions for the current collaboration. No tests or code changes yet.
- Reviewed `docker/docker-compose.yml` and `docker/start_service.sh` to confirm container responsibilities; no code changes made, no tests run.
- Consulted `Augmented_README.md` for Streamlit launch instructions; no code changes made, no tests run.
- Searched repository for `bootstrap.py`; file not found, no code changes made, no tests run.
- Command `python tools/bootstrap_env.py --help` failed (python not in PATH); retried with `python3` to inspect bootstrap CLI options; no code changes, no tests.
- Recommended using `python3 tools/bootstrap_env.py start --only streamlit` (or full `start`) to launch Streamlit via the bootstrap supervisor; no code changes, no tests.
- Checked `python3 tools/bootstrap_env.py status` (all services idle/missing).
- Confirmed `ANTHROPIC_API_KEY` not set in current shell (`<unset>`). No code changes, no tests run.
- Updated `computer-use-demo/computer_use_demo/streamlit.py` to expose only Anthropic and Local provider options and relabel OpenAI as Local in the UI; no tests run.
- Updated `computer-use-demo/computer_use_demo/tools/computer.py` and `.../tools/collection.py` to retain coordinates for click actions so the agent can left-click specific points; no automated tests run yet.
- Extended Streamlit dashboard with an execution mode selector wired through `sampling_loop`, evaluator init, and headless runner (`streamlit.py`, `loop.py`, `run_pure_computer_use_with_eval.py`); tests not run.
- Added `docker/apps_install_scripts/freetube.sh` to build FreeTube from source and install the generated `.deb`; tests not run.
- Created `Streamlined_README.md` with concise startup steps for Docker and Streamlit via `bootstrap_env.py`; no tests run.
- Expanded `Streamlined_README.md` with monitoring guidance (tail evaluator logs, inspect result JSON) for headless runs; no tests run.
- Updated `docker/apps_install_scripts/freetube.sh` to auto-source NVM, inject the missing `socket.io-client` dependency during build, and restore manifests afterward; local test still requires Node/Yarn to be present.
- Hooked FreeTube installer into `docker/start_service.sh` so Docker startup automatically builds/installs the app; no runtime tests executed.
- Added `INSTALL_APPS` toggle to `docker/docker-compose.yml` and gated installers in `start_service.sh`; documented usage in `Streamlined_README.md`. No automated tests run.
- Updated `docker/apps_install_scripts/freetube.sh` to use passworded sudo (default 123) for rpm/dpkg, failing clearly if installation still needs manual authorization, and now drop a sandbox-free wrapper in `/workspace/bin`. Also prepend `/workspace/bin` to PATH in `docker/start_service.sh` and documented the change.
- Hardened Streamlit API response viewer to tolerate binary bodies (e.g., screenshots) by falling back to size metadata instead of attempting UTF-8 decode.
- Patched `docker/apps_install_scripts/freetube.sh` so the generated no-sandbox wrapper also rewrites the FreeTube desktop entry and desktop shortcut to point at `/workspace/bin/freetube`, ensuring the GUI launcher inside noVNC works.

## FreeTube

- Ran `python computer-use-demo/run_pure_computer_use_with_eval.py --api_key "$ANTHROPIC_KEY" --model claude-3-7-sonnet-20250219 --task_id FreeTube/task01_search --app_path /workspace/bin/freetube --log_dir logs_computer_use_eval --exec_mode mixed` to verify task01 in the headless runner. This was successful.
- Confirmed the same task succeeds in API-only mode (`--exec_mode api`), so both interaction profiles are green.
- Preparing to evaluate FreeTube with the local Ollama-backed LLM using:
  `python computer-use-demo/run_pure_computer_use_with_eval.py --provider openai --openai_api_key ollama --openai_base_url http://localhost:11434 --openai_endpoint /v1/chat/completions --model qwen2.5:7b-instruct --task_id FreeTube/task01_search --app_path /workspace/bin/freetube --log_dir logs_computer_use_eval --exec_mode api`.
  Goal is to confirm the API-only flow works end-to-end with the local provider.
