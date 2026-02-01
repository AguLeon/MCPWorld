#!/usr/bin/env python3
"""
Background GPU & container CPU monitoring script.
Polls nvidia-smi and docker stats at a configurable interval and writes
timestamped metrics to CSV.

Usage:
    python3 scripts/monitor_gpu.py <output_csv> [interval_seconds]

The process runs until killed (SIGTERM/SIGINT).
"""

from __future__ import annotations

import csv
import subprocess
import sys
import time

NVIDIA_SMI_QUERY = "utilization.gpu,memory.used,temperature.gpu,power.draw"
CSV_HEADER = ["timestamp", "gpu_util_pct", "vram_mb", "temp_c", "power_w", "container_cpu_pct", "container_mem_mb"]

DOCKER_STATS_CMD = 'docker stats ollama --no-stream --format "{{.CPUPerc}},{{.MemUsage}}"'


def poll_gpu(cmd: str) -> list[str] | None:
    """Run nvidia-smi and return parsed values, or None on failure."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return None
        values = [v.strip() for v in result.stdout.strip().split(",")]
        if len(values) != 4:
            return None
        return values
    except Exception:
        return None


def poll_container_cpu() -> list[str]:
    """Poll docker stats for ollama container CPU% and memory.

    Returns [cpu_pct, mem_mb] or ["", ""] on failure.
    """
    try:
        result = subprocess.run(
            DOCKER_STATS_CMD, shell=True, capture_output=True, text=True, timeout=5
        )
        if result.returncode != 0:
            return ["", ""]
        # Output like: "152.30%,4.567GiB / 15.6GiB"
        parts = result.stdout.strip().split(",")
        if len(parts) != 2:
            return ["", ""]
        cpu_pct = parts[0].replace("%", "").strip()
        # Parse memory: "4.567GiB / 15.6GiB" -> take used portion
        mem_str = parts[1].strip().split("/")[0].strip()
        mem_mb = _parse_mem_to_mb(mem_str)
        return [cpu_pct, str(mem_mb) if mem_mb is not None else ""]
    except Exception:
        return ["", ""]


def _parse_mem_to_mb(mem_str: str) -> float | None:
    """Convert docker memory string like '4.567GiB' or '512MiB' to MB."""
    mem_str = mem_str.strip()
    try:
        if mem_str.endswith("GiB"):
            return round(float(mem_str[:-3]) * 1024, 1)
        elif mem_str.endswith("MiB"):
            return round(float(mem_str[:-3]), 1)
        elif mem_str.endswith("KiB"):
            return round(float(mem_str[:-3]) / 1024, 2)
        elif mem_str.endswith("B"):
            return round(float(mem_str[:-1]) / (1024 * 1024), 2)
        return None
    except (ValueError, IndexError):
        return None


CPU_POLL_INTERVAL = 1.0  # docker stats minimum practical interval


def monitor(output_csv: str, interval: float = 0.25) -> None:
    """Poll nvidia-smi at `interval` and docker stats at ~1s, write to CSV.

    GPU rows are written every `interval` seconds. CPU columns are refreshed
    every ~1s (CPU_POLL_INTERVAL) and the last known values are repeated on
    intermediate GPU rows.
    """
    # Try docker exec first, fall back to local nvidia-smi
    docker_cmd = (
        f"docker exec ollama nvidia-smi --query-gpu={NVIDIA_SMI_QUERY} "
        f"--format=csv,noheader,nounits"
    )
    local_cmd = (
        f"nvidia-smi --query-gpu={NVIDIA_SMI_QUERY} --format=csv,noheader,nounits"
    )

    # Determine which GPU command works (if any)
    gpu_cmd = None
    if poll_gpu(docker_cmd) is not None:
        gpu_cmd = docker_cmd
    elif poll_gpu(local_cmd) is not None:
        gpu_cmd = local_cmd

    if gpu_cmd is None:
        print("[monitor] WARNING: No GPU detected, collecting CPU/container metrics only", file=sys.stderr)

    last_cpu_values = ["", ""]
    last_cpu_poll = 0.0

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)

        try:
            while True:
                now = time.time()

                if gpu_cmd is not None:
                    gpu_values = poll_gpu(gpu_cmd)
                else:
                    gpu_values = None
                gpu_row = gpu_values if gpu_values is not None else ["", "", "", ""]

                # Refresh CPU metrics at ~1s intervals
                if now - last_cpu_poll >= CPU_POLL_INTERVAL:
                    last_cpu_values = poll_container_cpu()
                    last_cpu_poll = now

                writer.writerow([time.time()] + gpu_row + last_cpu_values)
                f.flush()
                time.sleep(interval)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <output_csv> [interval_seconds]", file=sys.stderr)
        sys.exit(1)

    output_path = sys.argv[1]
    poll_interval = float(sys.argv[2]) if len(sys.argv) > 2 else 1.0
    monitor(output_path, poll_interval)
