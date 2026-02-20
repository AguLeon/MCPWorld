#!/usr/bin/env python3
"""
Script to convert benchmark result JSON files to tabular CSV format.
Filename format: result_{model_name}_{infrastructure}_{task_id}_{task_name}_{timestamp}.json
"""

import json
import csv
import os
from pathlib import Path
from typing import Any


def _get_error_types(data: dict) -> str:
    """
    Helper function to get error types as a single string
    """
    err = data.get("errors_by_source", {}) or {}
    if err == {}:
        return ""

    return ", ".join(list(err.keys()))


def _get_most_tool(data: dict) -> tuple[str, int]:
    total = 0
    most_tool = ""

    tools = data.get("tools", {}) or {}
    for tool in tools:
        if (curr_count := data.get("tools").get(tool)["total_count"]) > total:
            total = curr_count
            most_tool = tool

    return most_tool, total


def safe_get(data: dict, *keys, default=None) -> Any:
    """Safely navigate nested dictionary structure."""
    current = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return default
    return current


def extract_row_from_json(filepath: str, base_dir: str = None) -> dict[str, Any]:
    """Extract a single row of data from a JSON result file."""

    # Load JSON data
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Extract metadata
    metadata = data.get("metadata", {})
    infra_tag = (
        metadata.get("infrastructure_tag", "")
        if metadata.get("infrastructure_tag", "") != ""
        else "N/A"
    )
    task_config = metadata.get("task_config_at_start", {})
    computed_metrics = data.get("computed_metrics", {})

    # Extract key step tracker
    key_step_tracker = computed_metrics.get("key_step_tracker", {})

    # Extract LLM token usage
    llm_token_usage = computed_metrics.get("llm_token_usage", {})

    # Extract generation time metrics
    gen_time_metrics = computed_metrics.get("generation_time_metrics", {})

    # Extract processing overhead metrics
    overhead_metrics = computed_metrics.get("processing_overhead_metrics", {})

    # Extract token efficiency metrics
    token_efficiency = computed_metrics.get("token_efficiency_metrics", {})

    # Extract throughput metrics
    throughput_metrics = computed_metrics.get("throughput_metrics", {})

    # Extract tool confidence metrics
    tool_confidence = computed_metrics.get("tool_confidence_metrics", {})

    # Extract tool usage stats
    tool_usage = computed_metrics.get("tool_usage_stats", {})
    most_used_tool, most_used_tool_count = _get_most_tool(tool_usage)

    # Extract error summary
    error_summary = computed_metrics.get("error_summary", {})

    # Extact ttft metrics
    ttft_metrics = computed_metrics.get("ttft_metrics", {})

    # Extract hallucination metrics
    hallucination_metrics = computed_metrics.get("tool_hallucination_metrics", {})

    # Extract loop detection metrics
    loop_metrics = computed_metrics.get("loop_detection_metrics", {})

    # Extract GPU hardware metrics (if available)
    gpu_metrics = data.get("gpu_hardware_metrics", {})

    # Extract cost metrics
    cost_metrics = computed_metrics.get("cost_metrics", {})

    # Build row
    row = {
        # Session metadata
        "model_name": metadata.get("model_name", ""),
        "temperature": metadata.get("temperature", None),
        "infrastructure_tag": infra_tag,
        "session_start_iso": metadata.get("session_start_iso", ""),
        "session_end_iso": metadata.get("session_end_iso", ""),
        "session_duration_seconds": metadata.get("session_duration_seconds", None),
        # Task configuration
        "task_id": task_config.get("task_id", ""),
        "task_name": task_config.get("task_name", ""),
        "task_description": task_config.get("description", ""),
        "application_name": safe_get(
            task_config, "application_info", "name", default=""
        ),
        "total_key_steps": task_config.get("total_key_steps", None),
        "exec_mode": task_config.get("exec_mode", ""),
        # Completion metrics
        "task_status": safe_get(
            computed_metrics, "task_completion_status", "status", default=""
        ),
        "task_remark": safe_get(
            computed_metrics, "task_completion_status", "reason", default=""
        ),
        "agent_reported_completion": safe_get(
            computed_metrics,
            "agent_reported_completion",
            "reasoning",
            default="",
        ),
        "completed_steps_count": key_step_tracker.get("completed_steps_count", None),
        "highest_index_reached": key_step_tracker.get("highest_index_reached", None),
        "completion_rate_by_count": key_step_tracker.get(
            "completion_rate_by_count", None
        ),
        "completion_rate_by_progress": key_step_tracker.get(
            "completion_rate_by_progress", None
        ),
        "final_step_reached": key_step_tracker.get("final_step_reached", None),
        # LLM metrics
        "llm_call_count": computed_metrics.get("llm_call_count", None),
        "total_prompt_tokens": llm_token_usage.get("total_prompt_tokens", None),
        "total_completion_tokens": llm_token_usage.get("total_completion_tokens", None),
        "total_tokens": llm_token_usage.get("total_tokens", None),
        # Token efficiency
        "average_tokens_per_call": token_efficiency.get(
            "average_tokens_per_call", None
        ),
        "token_efficiency_ratio": token_efficiency.get("token_efficiency_ratio", None),
        # Throughput metrics
        "avg_tokens_per_second": throughput_metrics.get("avg_tokens_per_second", None),
        "min_tokens_per_second": throughput_metrics.get("min_tokens_per_second", None),
        "max_tokens_per_second": throughput_metrics.get("max_tokens_per_second", None),
        "overall_tokens_per_second": throughput_metrics.get(
            "overall_tokens_per_second", None
        ),
        "total_generation_time_sec": throughput_metrics.get(
            "total_generation_time_sec", None
        ),
        # Tool confidence metrics
        "avg_tool_confidence": tool_confidence.get("avg_tool_confidence", None),
        "min_tool_confidence": tool_confidence.get("min_tool_confidence", None),
        "max_tool_confidence": tool_confidence.get("max_tool_confidence", None),
        # Performance metrics
        "total_duration_seconds": computed_metrics.get("total_duration_seconds", None),
        "average_generation_time_ms": gen_time_metrics.get(
            "average_generation_time_ms", None
        ),
        "min_generation_time_ms": gen_time_metrics.get("min_generation_time_ms", None),
        "max_generation_time_ms": gen_time_metrics.get("max_generation_time_ms", None),
        "all_generation_times_ms": gen_time_metrics.get("all_generation_times_ms", []),
        # Overhead metrics
        "total_llm_time_ms": overhead_metrics.get("total_llm_time_ms", None),
        "total_task_time_ms": overhead_metrics.get("total_task_time_ms", None),
        "total_tool_time_ms": overhead_metrics.get("total_tool_time_ms", None),
        "processing_overhead_ms": overhead_metrics.get("processing_overhead_ms", None),
        "overhead_percentage": overhead_metrics.get("overhead_percentage", None),
        # Tool usage
        "total_tool_calls": tool_usage.get("total_tool_calls", 0),
        "unique_tools_used": len(tool_usage.get("tools", {}).keys()),
        "tool_names_used": ", ".join(list(tool_usage.get("tools", {}).keys())),
        "most_used_tool": most_used_tool,
        "most_used_tool_count": most_used_tool_count,
        # Error & quality metrics
        "error_count": error_summary.get("total_error_count", None),
        "error_types": _get_error_types(error_summary),
        # TTFT metrics
        "average_ttft_ms": ttft_metrics.get("average_ttft_ms", None),
        "min_ttft_ms": ttft_metrics.get("min_ttft_ms", None),
        "max_ttft_ms": ttft_metrics.get("max_ttft_ms", None),
        "all_ttft_ms": ttft_metrics.get("all_ttft_ms", []),
        # Hallucination Metrics
        "hallucination_detected": hallucination_metrics.get(
            "hallucination_detected", None
        ),
        "total_hallucinated_calls": hallucination_metrics.get(
            "total_hallucinated_calls", None
        ),
        "hallucinated_tool_names": ", ".join(
            hallucination_metrics.get("hallucinated_tool_names", [])
        )
        if hallucination_metrics.get("hallucinated_tool_names")
        else "",
        # Loop Detection
        "loop_detected": loop_metrics.get("loop_detected", None),
        "total_loop_detections": loop_metrics.get("total_loop_detections", None),
        "loop_types": list(loop_metrics.get("loop_types", {}).keys()),
        # Cost metrics
        # "total_cost_usd": cost_metrics.get("total_cost", None),
        # "prompt_cost_usd": cost_metrics.get("prompt_cost", None),
        # "completion_cost_usd": cost_metrics.get("completion_cost", None),
        # GPU hardware metrics (optional - only present for GPU runs)
        "gpu_avg_util_pct": gpu_metrics.get("avg_gpu_util_pct", None),
        "gpu_max_util_pct": gpu_metrics.get("max_gpu_util_pct", None),
        "gpu_min_util_pct": gpu_metrics.get("min_gpu_util_pct", None),
        "gpu_avg_vram_mb": gpu_metrics.get("avg_vram_mb", None),
        "gpu_peak_vram_mb": gpu_metrics.get("peak_vram_mb", None),
        "gpu_min_vram_mb": gpu_metrics.get("min_vram_mb", None),
        "gpu_avg_temp_c": gpu_metrics.get("avg_temp_c", None),
        "gpu_max_temp_c": gpu_metrics.get("max_temp_c", None),
        "gpu_avg_power_w": gpu_metrics.get("avg_power_w", None),
        "gpu_max_power_w": gpu_metrics.get("max_power_w", None),
        "gpu_total_energy_joules": gpu_metrics.get("total_energy_joules", None),
        "gpu_total_energy_kwh": gpu_metrics.get("total_energy_kwh", None),
        "gpu_energy_h1_joules": gpu_metrics.get("energy_h1_joules", None),
        "gpu_energy_h2_joules": gpu_metrics.get("energy_h2_joules", None),
        "gpu_avg_power_h1_w": gpu_metrics.get("avg_power_h1_w", None),
        "gpu_avg_power_h2_w": gpu_metrics.get("avg_power_h2_w", None),
        "gpu_energy_rate_ratio_h2_h1": gpu_metrics.get("energy_rate_ratio_h2_h1", 0.0)
        or 0.0,
        "gpu_energy_q1_joules": gpu_metrics.get("energy_q1_joules", None),
        "gpu_energy_q2_joules": gpu_metrics.get("energy_q2_joules", None),
        "gpu_energy_q3_joules": gpu_metrics.get("energy_q3_joules", None),
        "gpu_energy_q4_joules": gpu_metrics.get("energy_q4_joules", None),
        "gpu_energy_q5_joules": gpu_metrics.get("energy_q5_joules", None),
        "gpu_avg_power_q1_w": gpu_metrics.get("avg_power_q1_w", None),
        "gpu_avg_power_q2_w": gpu_metrics.get("avg_power_q2_w", None),
        "gpu_avg_power_q3_w": gpu_metrics.get("avg_power_q3_w", None),
        "gpu_avg_power_q4_w": gpu_metrics.get("avg_power_q4_w", None),
        "gpu_avg_power_q5_w": gpu_metrics.get("avg_power_q5_w", None),
        "gpu_energy_rate_ratio_q4_q2": gpu_metrics.get("energy_rate_ratio_q4_q2", 0.0)
        or 0.0,
        "gpu_avg_vram_h1_mb": gpu_metrics.get("avg_vram_h1_mb", None),
        "gpu_avg_vram_h2_mb": gpu_metrics.get("avg_vram_h2_mb", None),
        "gpu_vram_ratio_h2_h1": gpu_metrics.get("vram_ratio_h2_h1", 0.0) or 0.0,
        "gpu_avg_vram_q1_mb": gpu_metrics.get("avg_vram_q1_mb", None),
        "gpu_avg_vram_q2_mb": gpu_metrics.get("avg_vram_q2_mb", None),
        "gpu_avg_vram_q3_mb": gpu_metrics.get("avg_vram_q3_mb", None),
        "gpu_avg_vram_q4_mb": gpu_metrics.get("avg_vram_q4_mb", None),
        "gpu_avg_vram_q5_mb": gpu_metrics.get("avg_vram_q5_mb", None),
        "gpu_vram_ratio_q4_q2": gpu_metrics.get("vram_ratio_q4_q2", 0.0) or 0.0,
        "gpu_sample_count": gpu_metrics.get("sample_count", None),
        "gpu_monitoring_duration_sec": gpu_metrics.get("monitoring_duration_sec", None),
        "container_avg_cpu_pct": gpu_metrics.get("avg_container_cpu_pct", None),
        "container_max_cpu_pct": gpu_metrics.get("max_container_cpu_pct", None),
        "container_avg_mem_mb": gpu_metrics.get("avg_container_mem_mb", None),
        "container_peak_mem_mb": gpu_metrics.get("peak_container_mem_mb", None),
    }

    return row


def process_directory(input_dir: str, output_csv: str, verbose: bool = True) -> None:
    """
    Process all JSON files in a directory and create a CSV file.

    Args:
        input_dir: Directory containing JSON result files
        output_csv: Path to output CSV file
        verbose: Print progress information
    """

    # Find all JSON files matching the pattern (recursively)
    json_files = []
    for file in Path(input_dir).rglob("*.json"):
        if file.name.startswith("result_"):
            json_files.append(str(file))

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    if verbose:
        print(f"Found {len(json_files)} JSON files to process")

    # Process each file
    rows = []
    for filepath in sorted(json_files):
        if verbose:
            print(f"Processing: {os.path.basename(filepath)}")
        try:
            row = extract_row_from_json(filepath, base_dir=input_dir)
            rows.append(row)
        except Exception as e:
            print(f"ERROR processing {filepath}: {e}")
            continue

    if not rows:
        print("No data extracted from JSON files")
        return

    # Write to CSV
    fieldnames = list(rows[0].keys())

    with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    if verbose:
        print(f"\nSuccessfully created CSV with {len(rows)} rows")
        print(f"Output file: {output_csv}")
        print(f"Columns: {len(fieldnames)}")


def main():
    """Main function with example usage."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert benchmark result JSON files to CSV format",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Process current directory
  python json_to_csv.py

  # Process specific directory
  python json_to_csv.py -i /path/to/results -o results.csv

  # Quiet mode
  python json_to_csv.py -i /path/to/results -q
        """,
    )

    parser.add_argument(
        "-i",
        "--input-dir",
        default=".",
        help="Input directory containing JSON files (default: current directory)",
    )

    parser.add_argument(
        "-o",
        "--output",
        default="benchmark_results.csv",
        help="Output CSV file path (default: benchmark_results.csv)",
    )

    parser.add_argument(
        "-q", "--quiet", action="store_true", help="Suppress progress output"
    )

    args = parser.parse_args()

    process_directory(
        input_dir=args.input_dir, output_csv=args.output, verbose=not args.quiet
    )


if __name__ == "__main__":
    main()
