#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Headless script for running Computer Use Demo Agent.
(Integrated with PC-Canary Evaluator - Minimal intrusive version)
Supports multi-turn conversational interaction.
"""

import os
import sys
import argparse
import asyncio
import platform
import time
import json
import signal
from typing import List, Dict, Any, Optional, cast

# --- Add PC-Canary path (modify according to your actual path) ---
PC_CANARY_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'PC-Canary'))
if PC_CANARY_PATH not in sys.path:
    print(f"Adding PC-Canary path: {PC_CANARY_PATH}")
    sys.path.append(PC_CANARY_PATH)

# --- Import necessary modules ---
from anthropic import Anthropic
from anthropic.types.beta import (
    BetaMessageParam,
    BetaContentBlockParam,
    BetaTextBlockParam,
    BetaToolResultBlockParam,
    BetaToolUseBlockParam,
)

# Import core components from computer_use_demo
try:
    from computer_use_demo.loop import sampling_loop, SYSTEM_PROMPT, APIProvider
    from computer_use_demo.tools import (
        TOOL_GROUPS_BY_VERSION,
        ToolCollection,
        ToolResult,
        ToolVersion,
    )
except ImportError as e:
    print(f"Error: Unable to import computer_use_demo components. Please ensure the script is running in the correct environment or that the project is added to the PYTHONPATH.")
    print(f"Original error: {e}")
    sys.exit(1)

# --- Import Evaluator-related components ---
try:
    from evaluator.core.base_evaluator import BaseEvaluator, CallbackEventData
    from evaluator.core.events import AgentEvent
except ImportError as e:
    print(f"Error: Unable to import PC-Canary Evaluator components. Please ensure the PC-Canary path is correct and added to the PYTHONPATH.")
    print(f"Original error: {e}")
    sys.exit(1)

# --- Global flags (used for callback termination of loop) ---
evaluation_finished = False
evaluator_instance_for_signal: Optional[BaseEvaluator] = None  # For signal handling


def ensure_evaluation_completion(evaluator: Optional[BaseEvaluator], *, trigger_hook: bool) -> bool:
    """
    Guarantee that we either receive the injected evaluate_on_completion event or fall back to manual detection.
    """
    global evaluation_finished
    if (
        not evaluator
        or not getattr(evaluator, "hook_manager", None)
        or not getattr(evaluator.hook_manager, "evaluate_on_completion", False)
        or evaluation_finished
    ):
        return False

    completed_via_hook = False
    if trigger_hook:
        evaluator.hook_manager.trigger_evaluate_on_completion()
        completed_via_hook = evaluation_finished

    return completed_via_hook


# --- Simple console callback functions ---
def headless_output_callback(block: BetaContentBlockParam) -> None:
    # (remains unchanged)
    if block['type'] == 'text':
        print(f"\nAssistant: {block['text']}")
    elif block['type'] == 'tool_use':
        print(f"\nAssistant wants to use Tool: {block['name']}")
        print(f"Input: {block['input']}")
    elif block['type'] == 'thinking':
        thinking_content = getattr(block, 'thinking', '...')
        print(f"\nAssistant [Thinking]:\n{thinking_content}\n")
    else:
        print(f"\n[Unknown output type]: {block}")

def headless_tool_output_callback(result: ToolResult, tool_id: str) -> None:
    # (remains unchanged, but note: TOOL_CALL events are now logged internally in loop.py)
    print(f"\n[Tool Result for ID: {tool_id}]")
    if result.output:
        if result.__class__.__name__ == "CLIResult":
            print(f"Output:\n```bash\n{result.output}\n```")
        else:
            print(f"Output: {result.output}")
    if result.error:
        print(f"Error: {result.error}")
    if result.base64_image:
        print("[Screenshot captured (omitted in headless mode)]")

def headless_api_response_callback(request, response, error) -> None:
    # (remains unchanged)
    if error:
        print(f"\n[API Error]: {error}")
    pass

# --- Evaluator callback function ---
def handle_evaluator_event(event_data: CallbackEventData, evaluator: BaseEvaluator):
    """Callback function to handle evaluator events"""
    print(f"\n[Evaluator Event]: {event_data.event_type} - {event_data.message}")
    global evaluation_finished
    if event_data.event_type in ["task_completed", "task_error"]:
        print(f"Evaluator reported final status: {event_data.event_type}")
        evaluation_finished = True

# --- Signal handling function ---
def signal_handler(sig, frame):
    """Handle CTRL+C signal"""
    print("\n\nUser interrupted execution...")
    global evaluator_instance_for_signal
    if evaluator_instance_for_signal and evaluator_instance_for_signal.is_running:
        print("Stopping evaluator...")
        evaluator_instance_for_signal.stop()  # stop() handles saving and TASK_END(stopped)
        # stop_app() may also need to be called, depending on the task
        if hasattr(evaluator_instance_for_signal, 'stop_app'):
            evaluator_instance_for_signal.stop_app()
    sys.exit(0)

# --- Main Execution Function ---
async def run_agent_loop(args, evaluator: BaseEvaluator):  # <-- Accepting evaluator instance
    """Run the main asynchronous loop of the Agent"""
    global evaluation_finished  # Referencing the global flag

    provider = args.provider_enum
    api_key = args.resolved_api_key
    if not api_key:
        print("Error: API key not provided.")
        return

    tool_version = cast(ToolVersion, args.tool_version)
    tool_group = TOOL_GROUPS_BY_VERSION[tool_version]
    tool_collection = ToolCollection(*(ToolCls() for ToolCls in tool_group.tools))
    print(f"Using tool version: {tool_version}")

    # 2. Build the system prompt (remains unchanged)
    system_prompt_text = SYSTEM_PROMPT
    if args.system_prompt_suffix:
        system_prompt_text += " " + args.system_prompt_suffix
    # Note: sampling_loop will handle the system prompt block

    # 3. Initialize message history
    messages: List[BetaMessageParam] = []

    # 4. Start the multi-turn conversation loop (add evaluation_finished condition)
    turn_count = 0
    start_time = time.time()  # Record the loop start time for timeout checking
    is_timeout = lambda: args.timeout > 0 and time.time() - start_time > args.timeout
    while (args.max_turns is None or turn_count < args.max_turns) and not evaluation_finished:
        # Check for timeout (relative to the loop start)
        if is_timeout():
            print(f"\nExecution timed out ({args.timeout} seconds)")
            break  # Let finally handle stopping

        print("-" * 30)
        # Get user input
        try:
            user_input = ""
            if turn_count == 0:
                default_instr = evaluator.default_instruction
                if default_instr:
                    prompt = f'You (Press Enter for default: "{default_instr}"): '
                    user_input = input(prompt)
                    if not user_input.strip():  # If user just pressed Enter or input was blank
                        print(f"Using default instruction: {default_instr}")
                        user_input = default_instr
                else:
                    # If no default instruction, normal prompt
                    user_input = input("You: ")
            else:
                # For non-first turns, normal prompt
                user_input = input("You: ")

            if user_input.lower() in ["quit", "exit"]:
                print("User requested exit.")
                break  # Exit loop normally
        except EOFError:
            print("\nEOF detected, exiting.")
            break

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
        if turn_count == 0 and "computer" in tool_collection.tool_map and args.exec_mode != "api":
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

        # --- Event recording: LLM call starts ---
        llm_start_time = time.time()
        model_name_to_record = args.model  # Or try to get it from the client
        evaluator.record_event(AgentEvent.LLM_QUERY_START, {
            'timestamp': llm_start_time,
            'model_name': model_name_to_record
        })

        print("Assistant thinking...")
        llm_success = False
        llm_error = None
        usage_info = None  # Initialize usage_info
        try:
            # --- Call core sampling_loop ---
            # Need to pass evaluator and task_id for internal TOOL event recording
            messages = await sampling_loop(
                model=args.model,
                provider=provider,
                messages=messages,
                output_callback=headless_output_callback,
                tool_output_callback=headless_tool_output_callback,  # Tool result printing
                api_response_callback=headless_api_response_callback,
                api_key=api_key,
                tool_version=tool_version,
                max_tokens=args.max_tokens,
                system_prompt_suffix=args.system_prompt_suffix,
                evaluator=evaluator,                # <--- Pass evaluator
                evaluator_task_id=evaluator.task_id,  # <--- Pass task ID
                is_timeout=is_timeout,
                only_n_most_recent_images=None,
                thinking_budget=None,
                token_efficient_tools_beta=False,
                exec_mode=args.exec_mode,
                # TODO: Try making sampling_loop return usage_info
            )
            # Assume if no exception is thrown in sampling_loop, the LLM call was successful
            # But we don't directly get usage_info
            llm_success = True
            # print(f"Debug: messages after loop: {messages}")  # For debugging
        except Exception as e:
            print(f"\n[Error during agent loop]: {e}")
            llm_error = str(e)
            # break  # Exit loop on error

        # --- Event recording: LLM call ends ---
        # Temporarily unable to get exact tokens, record None
        evaluator.record_event(AgentEvent.LLM_QUERY_END, {
            'timestamp': time.time(),
            'status': 'success' if llm_success else 'error',
            'error': llm_error,
            'prompt_tokens': None,  # <-- Missing
            'completion_tokens': None,  # <-- Missing
            'cost': None
        })

        # --- Check if the Agent reports completion (simple example, needs to be adjusted based on actual output) ---
        # if messages:
        #     last_assistant_message = messages[-1]
        #     if last_assistant_message['role'] == 'assistant':
        #        # ... Parse last_assistant_message['content'] ...
        #        # if "task complete" in text_content:
        #        #     evaluator.record_event(AgentEvent.AGENT_REPORTED_COMPLETION, ...)
        #        pass

        turn_count += 1
        time.sleep(1)  # Short sleep to avoid high CPU usage and give callbacks time

    ensure_evaluation_completion(evaluator, trigger_hook=True)

# --- Command-Line Argument Parsing and Main Function ---
if __name__ == "__main__":
    available_tool_versions = ["computer_use_20250124", "computer_only", "computer_use_20241022"]

    parser = argparse.ArgumentParser(description="Run Computer Use Demo Agent Headlessly with Evaluator")
    # Agent Arguments
    provider_choices = [provider.value for provider in APIProvider]
    parser.add_argument("--provider", type=str, default=APIProvider.ANTHROPIC.value, choices=provider_choices, help="LLM provider to use")
    parser.add_argument("--api_key", type=str, default=None, help="Anthropic API Key (or use ANTHROPIC_API_KEY env var)")
    parser.add_argument("--openai_api_key", type=str, default=None, help="OpenAI-compatible API Key (or use OPENAI_API_KEY env var)")
    parser.add_argument("--openai_base_url", type=str, default=None, help="OpenAI-compatible base URL (default: env OPENAI_BASE_URL or https://api.openai.com)")
    parser.add_argument("--openai_endpoint", type=str, default=None, help="OpenAI-compatible endpoint path (default: env OPENAI_ENDPOINT or /v1/chat/completions)")
    parser.add_argument("--openai_tool_choice", type=str, default=None, choices=["auto", "none"], help="OpenAI-compatible tool_choice parameter")
    parser.add_argument("--openai_timeout", type=float, default=None, help="Timeout in seconds for OpenAI-compatible requests")
    parser.add_argument("--openai_response_format", type=str, default=None, help="JSON string to pass as response_format for OpenAI-compatible requests")
    parser.add_argument("--model", type=str, default="claude-3-7-sonnet-20250219", help="Model name for the selected provider")
    parser.add_argument("--tool_version", type=str, default=available_tool_versions[0], choices=available_tool_versions, help="Version of tools to use")
    parser.add_argument("--max_tokens", type=int, default=4096, help="Max tokens for model response")
    parser.add_argument("--system_prompt_suffix", type=str, default="", help="Additional text to append to the system prompt")
    parser.add_argument("--max_turns", type=int, default=10, help="Maximum number of conversation turns (user + assistant, default: 10)")
    # Evaluator Arguments
    parser.add_argument("--task_id", type=str, required=True, help="PC-Canary Task ID (format: category/id, e.g., computeruse/task01_example)")
    parser.add_argument("--log_dir", type=str, default="logs_computer_use_eval", help="Directory for evaluator logs and results")
    parser.add_argument("--app_path", type=str, default=None, help="Path to specific application if required by the task")
    parser.add_argument("--timeout", type=int, default=600, help="Overall execution timeout in seconds (default: 600)")
    parser.add_argument("--exec_mode", type=str, choices=["mixed", "gui", "api"], default="mixed", 
                        help="Agent mode for tool use evaluation (default: mixed)")

    args = parser.parse_args()

    provider_enum = APIProvider(args.provider)
    args.provider_enum = provider_enum

    if provider_enum == APIProvider.OPENAI:
        api_key = args.openai_api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            print("Error: OpenAI-compatible API key must be provided (--openai_api_key or OPENAI_API_KEY environment variable)")
            sys.exit(1)
        base_url = args.openai_base_url or os.getenv("OPENAI_BASE_URL", "https://api.openai.com")
        endpoint = args.openai_endpoint or os.getenv("OPENAI_ENDPOINT", "/v1/chat/completions")
        tool_choice = args.openai_tool_choice or os.getenv("OPENAI_TOOL_CHOICE", "auto")
        if tool_choice not in {"auto", "none"}:
            tool_choice = "auto"
        timeout = args.openai_timeout
        if timeout is None:
            timeout_env = os.getenv("OPENAI_TIMEOUT")
            if timeout_env:
                try:
                    timeout = float(timeout_env)
                except ValueError:
                    timeout = None
        response_format = args.openai_response_format or os.getenv("OPENAI_RESPONSE_FORMAT", "")

        os.environ["OPENAI_API_KEY"] = api_key
        os.environ["OPENAI_BASE_URL"] = base_url
        os.environ["OPENAI_ENDPOINT"] = endpoint
        os.environ["OPENAI_TOOL_CHOICE"] = tool_choice
        if timeout is not None:
            os.environ["OPENAI_TIMEOUT"] = str(timeout)
        if response_format:
            os.environ["OPENAI_RESPONSE_FORMAT"] = response_format
        elif "OPENAI_RESPONSE_FORMAT" in os.environ and not response_format:
            os.environ.pop("OPENAI_RESPONSE_FORMAT", None)

        if args.model == "claude-3-7-sonnet-20250219":
            args.model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o")

        args.resolved_api_key = api_key
    else:
        api_key = args.api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: Anthropic API key must be provided (--api_key or ANTHROPIC_API_KEY environment variable)")
            sys.exit(1)
        args.resolved_api_key = api_key
    
    if not os.getenv("DISPLAY"):
        print("Error: DISPLAY environment variable must be provided")
        sys.exit(1)

    # Parse task_id
    try:
        category, task_id_part = args.task_id.split('/', 1)
        task_config = {"category": category, "id": task_id_part}
    except ValueError:
        print("Error: task_id format must be 'category/id'")
        sys.exit(1)

    # Create log directory
    os.makedirs(args.log_dir, exist_ok=True)

    # Initialize Evaluator
    evaluator: Optional[BaseEvaluator] = None  # Explicit type
    try:
        print(f"[*] Initializing evaluator (Task: {args.task_id})...")
        evaluator = BaseEvaluator(
            task=task_config,
            log_dir=args.log_dir,
            app_path=args.app_path,
            custom_params={"exec_mode": args.exec_mode},
        )
        evaluator.timeout = args.timeout
        evaluator_instance_for_signal = evaluator  # Assign to global variable for signal handling
        evaluator.register_completion_callback(handle_evaluator_event)
    except Exception as e:
        print(f"Failed to initialize evaluator: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Set up signal handling
    signal.signal(signal.SIGINT, signal_handler)

    try:
        # Start evaluator
        print("[*] Starting evaluator...")
        if not evaluator.start():
            print("Evaluator failed to start!")
            sys.exit(1)

        # Wait for internal evaluator initialization (e.g., starting the app)
        wait_time = 2  # seconds
        print(f"[*] Waiting {wait_time} seconds to ensure evaluator is ready...")
        time.sleep(wait_time)

        print("[*] Starting Agent interaction loop...")
        # Run the main loop
        asyncio.run(run_agent_loop(args, evaluator))  # Pass evaluator in

    except KeyboardInterrupt:
        print("\nMain program interrupted.")  # Signal handler will handle stopping
    except Exception as e:
        print(f"\nUnhandled error in main program: {e}")
        import traceback
        traceback.print_exc()
    finally:
        ensure_evaluation_completion(evaluator, trigger_hook=True)
        # Finally stop the evaluator (if still running)
        if evaluator and evaluator.is_running:
            print("[*] (Finally) Stopping evaluator...")
            evaluator.stop()
        if evaluator and hasattr(evaluator, 'stop_app'):
            print("[*] (Finally) Stopping associated app...")
            evaluator.stop_app()
        ensure_evaluation_completion(evaluator, trigger_hook=False)

        # Report final results
        if evaluator:
            print("\n" + "=" * 30 + " Evaluation Results " + "=" * 30)
            final_results = evaluator.result_collector.get_results(evaluator.task_id)
            computed_metrics = final_results.get('computed_metrics', {})
            final_status = computed_metrics.get('task_completion_status', {})

            print("Final Computed Metrics:")
            if computed_metrics:
                for key, value in computed_metrics.items():
                    try:
                        value_str = json.dumps(value, ensure_ascii=False, indent=2) if isinstance(value, (dict, list)) else str(value)
                    except TypeError:
                        value_str = str(value)  # Fallback for non-serializable types
                    print(f"  {key}: {value_str}")
            else:
                print("  No computed metrics available.")

            print(f"\nFinal Task Status: {final_status.get('status', 'Unknown')}")
            if final_status.get('reason'):
                print(f"Reason: {final_status.get('reason')}")

            # Result file path is usually printed in evaluator.stop() -> save_results()
            # result_file = evaluator.save_results()  # No need to save again

        print("=" * 72)
        print("Script execution complete.")

