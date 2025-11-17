#!/usr/bin/env python3
"""
Helper script that parses a run result JSON file and appends summary + metrics
rows for vscode batch executions.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Dict

SUMMARY_HEADER = ["task_id", "status", "reason", "log_dir"]
METRICS_HEADER = [
    "task_id",
    "status",
    "reason",
    "total_duration_seconds",
    "llm_call_count",
    "total_tool_calls",
    "total_error_count",
    "total_steps",
    "completed_steps",
    "log_dir",
]


def _load_metrics(result_file: Path) -> Dict[str, Any]:
    if not result_file or not result_file.exists():
        return {}
    try:
        with result_file.open("r", encoding="utf-8") as fh:
            return json.load(fh).get("computed_metrics", {}) or {}
    except Exception:
        return {}


def _sanitize(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (int, float)):
        return str(value)
    return str(value).replace("\n", " ").replace(",", ";").strip()


def _append_row(csv_path: Path, header: list[str], row: list[str]) -> None:
    needs_header = not csv_path.exists() or csv_path.stat().st_size == 0
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        if needs_header:
            writer.writerow(header)
        writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect VSCode task metrics.")
    parser.add_argument("--result", type=Path, default=None, help="Path to result_*.json")
    parser.add_argument("--task-id", required=True, help="Full task id, e.g. vscode/task01")
    parser.add_argument("--log-dir", required=True, help="Directory containing evaluator logs")
    parser.add_argument("--summary", type=Path, required=True, help="Summary CSV path")
    parser.add_argument("--metrics", type=Path, required=True, help="Metrics CSV path")
    parser.add_argument("--fallback-status", default="unknown", help="Status when result is missing")
    parser.add_argument("--fallback-reason", default="", help="Reason when result is missing")
    args = parser.parse_args()

    computed = _load_metrics(args.result) if args.result else {}
    status = computed.get("task_completion_status", {}).get("status") or args.fallback_status
    reason = computed.get("task_completion_status", {}).get("reason") or args.fallback_reason

    total_duration = computed.get("total_duration_seconds")
    llm_calls = computed.get("llm_call_count")

    tool_usage = computed.get("tool_usage_stats", {}) or {}
    total_tool_calls = tool_usage.get("total_tool_calls")

    error_summary = computed.get("error_summary", {}) or {}
    total_error_count = error_summary.get("total_error_count")

    key_steps = computed.get("key_step_tracker", {}) or {}
    total_steps = key_steps.get("total_steps")
    completed_steps = key_steps.get("completed_steps_count")

    sanitized_reason = _sanitize(reason) or "n/a"

    summary_row = [
        _sanitize(args.task_id),
        _sanitize(status),
        sanitized_reason,
        _sanitize(args.log_dir),
    ]
    metrics_row = summary_row[:3] + [
        _sanitize(total_duration),
        _sanitize(llm_calls),
        _sanitize(total_tool_calls),
        _sanitize(total_error_count),
        _sanitize(total_steps),
        _sanitize(completed_steps),
        _sanitize(args.log_dir),
    ]

    _append_row(Path(args.summary), SUMMARY_HEADER, summary_row)
    _append_row(Path(args.metrics), METRICS_HEADER, metrics_row)


if __name__ == "__main__":
    main()
