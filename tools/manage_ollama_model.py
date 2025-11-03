#!/usr/bin/env python3
"""Manage Ollama models used by the computer-use demo."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from typing import Iterable, List, Set


def _require_ollama(cmd_override: str | None) -> str:
    if cmd_override:
        return cmd_override
    binary = shutil.which("ollama")
    if binary:
        return binary
    raise SystemExit("error: could not find `ollama` binary; install Ollama or pass --ollama-cmd")


def _run(cmd: List[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, check=check, text=True, capture_output=True)


def _parse_json_lines(output: str) -> List[dict]:
    rows: List[dict] = []
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _list_models(ollama_cmd: str) -> Set[str]:
    """Return the set of locally installed models."""
    try:
        result = _run([ollama_cmd, "list", "--format", "json"])
        items = json.loads(result.stdout)
        if isinstance(items, list):
            return {item["name"] for item in items if isinstance(item, dict) and "name" in item}
    except (subprocess.CalledProcessError, json.JSONDecodeError, KeyError):
        pass

    try:
        result = _run([ollama_cmd, "list"], check=False)
    except subprocess.CalledProcessError:
        return set()
    models: Set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("name"):
            continue
        parts = line.split()
        if parts:
            models.add(parts[0])
    return models


def _running_models(ollama_cmd: str) -> Set[str]:
    """Return the set of models that currently have running sessions."""
    try:
        result = _run([ollama_cmd, "ps", "--format", "json"])
        items = _parse_json_lines(result.stdout)
        return {item.get("name", "") for item in items if item.get("name")}
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        pass

    try:
        result = _run([ollama_cmd, "ps"], check=False)
    except subprocess.CalledProcessError:
        return set()
    models: Set[str] = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("name"):
            continue
        parts = line.split()
        if parts:
            models.add(parts[0])
    return models


def _stop_models(ollama_cmd: str, models: Iterable[str]) -> None:
    for model in models:
        if not model:
            continue
        print(f"Stopping running model: {model}")
        try:
            _run([ollama_cmd, "stop", model], check=False)
        except subprocess.CalledProcessError as err:
            print(f"  warning: failed to stop {model}: {err}", file=sys.stderr)


def _remove_models(ollama_cmd: str, models: Iterable[str]) -> None:
    for model in models:
        if not model:
            continue
        print(f"Removing local model: {model}")
        try:
            _run([ollama_cmd, "rm", model], check=False)
        except subprocess.CalledProcessError as err:
            print(f"  warning: failed to remove {model}: {err}", file=sys.stderr)


def manage_models(args: argparse.Namespace) -> int:
    ollama_cmd = _require_ollama(args.ollama_cmd)

    if args.pull:
        print(f"Pulling model: {args.model}")
        try:
            _run([ollama_cmd, "pull", args.model])
        except subprocess.CalledProcessError as err:
            print(err.stdout or err.stderr, file=sys.stderr)
            return err.returncode or 1

    running = _running_models(ollama_cmd)
    if running:
        print(f"Currently running models: {', '.join(sorted(running))}")
    else:
        print("No models currently running.")

    if args.stop_running and running:
        to_stop = {model for model in running if model != args.model}
        if args.stop_target:
            to_stop.add(args.model)
        _stop_models(ollama_cmd, to_stop)

    if args.evict_others:
        installed = _list_models(ollama_cmd)
        to_remove = {model for model in installed if model != args.model}
        if to_remove:
            _remove_models(ollama_cmd, sorted(to_remove))
        else:
            print("No additional models to evict.")

    if args.prune:
        print("Running `ollama prune` to reclaim disk space...")
        try:
            _run([ollama_cmd, "prune"], check=False)
        except subprocess.CalledProcessError as err:
            print(f"warning: prune failed: {err}", file=sys.stderr)

    if args.show_status:
        installed = _list_models(ollama_cmd)
        running = _running_models(ollama_cmd)
        print("\nSummary\n-------")
        print(f"Installed models: {', '.join(sorted(installed)) or 'None'}")
        print(f"Running models: {', '.join(sorted(running)) or 'None'}")

    print("Done. Configure OPENAI_DEFAULT_MODEL or Streamlit to use the new model as needed.")
    return 0


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Ollama models for the computer-use demo")
    parser.add_argument("--model", required=True, help="Target model to pull/keep (e.g., qwen2.5-vl:7b-instruct)")
    parser.add_argument("--ollama-cmd", help="Override path to the ollama binary")
    parser.add_argument(
        "--pull",
        dest="pull",
        action="store_true",
        help="Pull the requested model before switching (default: enabled).",
    )
    parser.add_argument(
        "--no-pull",
        dest="pull",
        action="store_false",
        help="Skip pulling the model (use if already present).",
    )
    parser.add_argument(
        "--stop-running",
        dest="stop_running",
        action="store_true",
        help="Stop other running models to free VRAM (default: enabled).",
    )
    parser.add_argument(
        "--no-stop-running",
        dest="stop_running",
        action="store_false",
        help="Do not stop other running models.",
    )
    parser.add_argument(
        "--stop-target",
        action="store_true",
        help="Also stop the target model if it is currently running.",
    )
    parser.add_argument(
        "--evict-others",
        action="store_true",
        help="Remove other installed models (ollama rm) to free disk/memory.",
    )
    parser.add_argument(
        "--prune",
        action="store_true",
        help="Run `ollama prune` after evicting other models.",
    )
    parser.add_argument(
        "--show-status",
        action="store_true",
        help="Print installed/running model summary after operations.",
    )

    parser.set_defaults(pull=True, stop_running=True)
    return parser


if __name__ == "__main__":
    parser = _build_arg_parser()
    arguments = parser.parse_args()
    try:
        sys.exit(manage_models(arguments))
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        sys.exit(130)
