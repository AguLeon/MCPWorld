#!/usr/bin/env python3
"""
Background GPU monitoring script.
Polls nvidia-smi at a configurable interval and writes timestamped metrics to CSV.

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
CSV_HEADER = ["timestamp", "gpu_util_pct", "vram_mb", "temp_c", "power_w"]


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


def monitor_gpu(output_csv: str, interval: float = 1.0) -> None:
    """Poll nvidia-smi and write metrics to CSV until interrupted."""
    # Try docker exec first, fall back to local nvidia-smi
    docker_cmd = (
        f"docker exec ollama nvidia-smi --query-gpu={NVIDIA_SMI_QUERY} "
        f"--format=csv,noheader,nounits"
    )
    local_cmd = (
        f"nvidia-smi --query-gpu={NVIDIA_SMI_QUERY} --format=csv,noheader,nounits"
    )

    # Determine which command works
    cmd = docker_cmd if poll_gpu(docker_cmd) is not None else local_cmd

    # Verify chosen command works
    if poll_gpu(cmd) is None:
        print(f"[monitor_gpu] ERROR: nvidia-smi not accessible via docker or locally", file=sys.stderr)
        sys.exit(1)

    with open(output_csv, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CSV_HEADER)

        try:
            while True:
                values = poll_gpu(cmd)
                if values is not None:
                    writer.writerow([time.time()] + values)
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
    monitor_gpu(output_path, poll_interval)
