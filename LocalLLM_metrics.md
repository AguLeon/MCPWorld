# Self-Hosted LLM Metrics Implementation Plan

**Document Purpose:** Comprehensive implementation guide for adding hardware and efficiency metrics to our self-hosted LLM benchmarking system.

**Last Updated:** 2026-02-01

**Status:** Planning Phase - Ready for Implementation

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Motivation: Why Self-Hosting Metrics Matter](#motivation)
3. [Current Architecture](#current-architecture)
4. [Phase 1 Metrics Overview](#phase-1-metrics-overview)
5. [Detailed Implementation Plan](#detailed-implementation-plan)
6. [Files to Modify](#files-to-modify)
7. [Data Flow Architecture](#data-flow-architecture)
8. [Testing & Validation](#testing--validation)
9. [Effort Estimate](#effort-estimate)
10. [Future Roadmap](#future-roadmap)

---

## Executive Summary

This document outlines a plan to enhance our LLM benchmarking system with **self-hosting exclusive metrics** - measurements that are impossible or impractical to obtain when using external API providers like Claude or GPT-4.

**Key Additions:**
- GPU hardware metrics (utilization, VRAM, temperature, power)
- Energy consumption tracking (joules, kWh)
- Inference throughput (tokens/second)
- Tool call confidence scores (via logprobs)

**Implementation Effort:** 10-13 hours

**Value Proposition:** These metrics enable deep analysis of model efficiency, cost optimization, and failure prediction that's unavailable with black-box API services.

---

## Motivation

### The Self-Hosting Advantage

When using external APIs (OpenAI, Anthropic, etc.), you get:
- ✅ Token counts
- ✅ Request latency
- ✅ API costs
- ❌ **NO** hardware utilization
- ❌ **NO** energy consumption
- ❌ **NO** model confidence scores

When self-hosting with Ollama, we have **direct access** to:
1. **GPU hardware** - via nvidia-smi
2. **Model internals** - via logprobs
3. **Inference engine** - via Ollama's API

This unlocks metrics that enable:
- **Energy efficiency analysis** - True $/task cost including electricity
- **Hardware optimization** - Identify GPU bottlenecks and underutilization
- **Model uncertainty quantification** - Predict failures from low confidence

### Use Cases

**Scenario 1: Model Selection**
- Compare 2B vs 32B models on energy per successful task
- Identify "sweet spot" for task complexity vs model size
- Calculate ROI vs API pricing

**Scenario 2: Failure Analysis**
- Correlate low tool confidence with task failures
- Identify which tasks cause model uncertainty
- Improve prompts for uncertain tool calls

**Scenario 3: Infrastructure Optimization**
- Detect GPU underutilization (bottleneck is elsewhere)
- Optimize batch sizes based on VRAM usage
- Identify thermal throttling during long runs

---

## Current Architecture

### Infrastructure

**Two-container Docker setup:**

```
┌─────────────────────────────────────────────────┐
│  mcpworld container                             │
│  - Runs benchmark tasks                         │
│  - Executes LLM agent loops                     │
│  - Collects metrics (events, timings, tokens)   │
│  - Saves result_*.json per task                 │
└─────────────────────────────────────────────────┘
                      │
                      │ HTTP: /v1/chat/completions
                      ▼
┌─────────────────────────────────────────────────┐
│  ollama container                               │
│  - Serves LLM models (Ollama)                   │
│  - OpenAI-compatible API                        │
│  - GPU support (NVIDIA)                         │
└─────────────────────────────────────────────────┘
```

### Current Metrics Collection

**Event-based logging:**
- `LLM_QUERY_START` / `LLM_QUERY_END` - LLM API calls with timing
- `LLM_FIRST_TOKEN_RECEIVED` - Time to first token (TTFT)
- `TOOL_CALL_START` / `TOOL_CALL_END` - Tool invocations
- `KEY_STEP_COMPLETED` - Task milestones

**Computed metrics:**
- Total duration, LLM call count, token counts
- Tool usage statistics, error counts
- Success/failure status
- Token efficiency ratios

**Storage:**
- **Primary:** `result_*.json` per task (event log + computed metrics)
- **Secondary:** `results.csv` aggregated across all tasks

### What's Missing

Currently **NOT** captured:
- ❌ GPU utilization %
- ❌ VRAM usage
- ❌ GPU temperature
- ❌ Power draw / energy consumption
- ❌ Tokens per second throughput
- ❌ Model confidence for tool calls

---

## Phase 1 Metrics Overview

### 1. GPU Hardware Metrics

**What:** Real-time GPU monitoring during task execution

**Metrics collected:**
- GPU utilization (%) - How hard the GPU is working
- VRAM usage (MB) - Memory consumed by model + KV cache
- GPU temperature (°C) - Thermal state
- Power draw (watts) - Instantaneous power consumption

**How:** Poll `nvidia-smi` every 1 second via background process

**Why it matters:**
- Identify GPU bottlenecks (low utilization = bottleneck elsewhere)
- Monitor memory constraints for model size optimization
- Detect thermal throttling

---

### 2. Energy Consumption

**What:** Total energy consumed per task

**Metrics collected:**
- Total energy (joules) - Integral of power over time
- Total energy (kWh) - For cost calculations

**Calculation:** `∑(power_watts × time_interval)`

**Why it matters:**
- True operational cost per task
- Compare energy efficiency across models
- Calculate ROI vs API pricing ($/kWh vs $/token)

---

### 3. Inference Throughput

**What:** Token generation speed

**Metrics collected:**
- Tokens per second - `completion_tokens / generation_time`

**Why it matters:**
- Model efficiency comparison
- Infrastructure performance benchmarking
- Identify slowdowns (GPU vs CPU vs I/O bound)

---

### 4. Tool Call Confidence

**What:** Model uncertainty when selecting tools

**Metrics collected:**
- Per-tool confidence score (0-1) - Based on logprobs
- Average confidence across all tool calls
- Minimum confidence (identifies uncertain decisions)

**How:** Enable `logprobs` in Ollama API, parse token probabilities

**Why it matters:**
- **Predict failures** - Low confidence correlates with errors
- **Improve prompts** - Identify ambiguous tool selection scenarios
- **Model comparison** - Larger models may be more confident
- **Self-hosting exclusive** - APIs don't expose logprobs for tool calls

---

## Detailed Implementation Plan

### Component 1: GPU Monitoring Script (2-3 hours)

#### **Create:** `scripts/monitor_gpu.py`

**Purpose:** Background process that polls GPU metrics during task execution

**Implementation:**

```python
#!/usr/bin/env python3
import subprocess
import time
import sys
import csv

def monitor_gpu(output_csv, interval=1.0):
    """
    Poll nvidia-smi and write metrics to CSV.

    Args:
        output_csv: Path to output CSV file
        interval: Polling interval in seconds (default 1.0)
    """
    # nvidia-smi query format
    query = "utilization.gpu,memory.used,temperature.gpu,power.draw"
    cmd = f"docker exec ollama nvidia-smi --query-gpu={query} --format=csv,noheader,nounits"

    with open(output_csv, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['timestamp', 'gpu_util_pct', 'vram_mb', 'temp_c', 'power_w'])

        try:
            while True:
                timestamp = time.time()
                result = subprocess.run(cmd, shell=True, capture_output=True, text=True)

                if result.returncode == 0:
                    # Parse output: "85, 4096, 72, 180"
                    values = [v.strip() for v in result.stdout.strip().split(',')]
                    writer.writerow([timestamp] + values)
                    f.flush()

                time.sleep(interval)
        except KeyboardInterrupt:
            pass

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: monitor_gpu.py <output_csv>")
        sys.exit(1)

    monitor_gpu(sys.argv[1])
```

**Integration:** Launched from `run_tasks_range.sh`:

```bash
# Before running task
GPU_LOG="${TASK_FOLDER}/gpu_metrics_${task_name}.csv"
python3 /workspace/scripts/monitor_gpu.py "$GPU_LOG" &
GPU_MONITOR_PID=$!

# Run task...

# After task completes
kill $GPU_MONITOR_PID 2>/dev/null || true
```

**Output format:**
```csv
timestamp,gpu_util_pct,vram_mb,temp_c,power_w
1738012345.123,85,4096,72,180
1738012346.123,87,4120,73,185
```

---

### Component 2: Throughput Metrics (1 hour)

#### **Modify:** `computer-use-demo/computer_use_demo/loop.py`

**Add to computed_metrics section:**

```python
# Calculate throughput (tokens per second)
total_completion_tokens = sum(event['data'].get('completion_tokens', 0)
                               for event in raw_events
                               if event['event'] == 'LLM_QUERY_END')

total_generation_time_ms = sum(event['data'].get('generation_time_ms', 0)
                                for event in raw_events
                                if event['event'] == 'LLM_QUERY_END')

total_generation_time_sec = total_generation_time_ms / 1000.0

if total_generation_time_sec > 0:
    throughput = total_completion_tokens / total_generation_time_sec
else:
    throughput = 0

computed_metrics['throughput_metrics'] = {
    'tokens_per_second': round(throughput, 2),
    'total_generation_time_sec': round(total_generation_time_sec, 2)
}
```

**Explanation:**
- **Throughput** = total output tokens ÷ total generation time
- Simple and effective metric for comparing model inference speed

---

### Component 3: GPU Metrics Integration (2-3 hours)

#### **Modify:** `scripts/run_tasks_range.sh`

**Add GPU monitoring launch/kill:**

```bash
# Inside task execution loop, before running task:

task_name=$(basename "$task_dir")
TASK_FOLDER="${RUN_FOLDER}/${task_name}_${CLEAN_MODEL_NAME}${INFRASTRUCTURE_SUFFIX}"
mkdir -p "$TASK_FOLDER"

# Start GPU monitoring
GPU_LOG="${TASK_FOLDER}/gpu_metrics_${task_name}.csv"
python3 /workspace/scripts/monitor_gpu.py "$GPU_LOG" &
GPU_MONITOR_PID=$!

echo "[INFO] Started GPU monitoring (PID: $GPU_MONITOR_PID) -> $GPU_LOG"

# Run task with timeout
timeout --signal=SIGTERM "${TOTAL_TIMEOUT}" \
    docker exec "$MCPWORLD_CONTAINER" bash -c "
        cd /workspace &&
        python3 run_pure_computer_use_with_eval.py \\
            --task_dir=\"$task_dir\" \\
            --log_dir=\"$TASK_FOLDER\" \\
            ...
    "

TASK_EXIT_CODE=$?

# Stop GPU monitoring
kill $GPU_MONITOR_PID 2>/dev/null || true
wait $GPU_MONITOR_PID 2>/dev/null

echo "[INFO] Stopped GPU monitoring"
```

**Important:** GPU monitor runs on **host** (not inside container) to access nvidia-smi

---

### Component 4: Result JSON Enhancement (1-2 hours)

#### **Modify:** `PC-Canary/evaluator/core/result_collector.py`

**Add helper function to parse GPU CSV:**

```python
def _parse_gpu_metrics_csv(gpu_log_path):
    """
    Parse GPU metrics CSV and compute aggregates.

    Returns dict with avg/max/min for all metrics, or None if file missing.
    """
    import pandas as pd
    import os

    if not os.path.exists(gpu_log_path):
        return None

    try:
        df = pd.read_csv(gpu_log_path)
        if df.empty:
            return None

        # Calculate energy: sum(power_watts × time_interval)
        # time_diff = difference between consecutive timestamps
        df['time_diff'] = df['timestamp'].diff().fillna(1.0)
        energy_joules = (df['power_w'] * df['time_diff']).sum()

        return {
            # GPU utilization
            'avg_gpu_util_pct': float(df['gpu_util_pct'].mean()),
            'max_gpu_util_pct': float(df['gpu_util_pct'].max()),
            'min_gpu_util_pct': float(df['gpu_util_pct'].min()),

            # VRAM
            'avg_vram_mb': float(df['vram_mb'].mean()),
            'peak_vram_mb': float(df['vram_mb'].max()),
            'min_vram_mb': float(df['vram_mb'].min()),

            # Temperature
            'avg_temp_c': float(df['temp_c'].mean()),
            'max_temp_c': float(df['temp_c'].max()),

            # Power
            'avg_power_w': float(df['power_w'].mean()),
            'max_power_w': float(df['power_w'].max()),

            # Energy
            'total_energy_joules': float(energy_joules),
            'total_energy_kwh': float(energy_joules / 3_600_000),  # J to kWh

            # Metadata
            'sample_count': len(df),
            'monitoring_duration_sec': float(df['timestamp'].max() - df['timestamp'].min())
        }
    except Exception as e:
        print(f"Error parsing GPU metrics from {gpu_log_path}: {e}")
        return None
```

**Integrate into save_results():**

```python
def save_results(self, task_id: str, filename_prefix: str = "result"):
    """Save results to JSON file with GPU metrics."""

    # ... existing code ...

    # Add GPU metrics if available
    gpu_metrics_file = os.path.join(self.output_dir, f"gpu_metrics_{task_id}.csv")
    gpu_metrics = _parse_gpu_metrics_csv(gpu_metrics_file)

    if gpu_metrics:
        self.results[task_id]['gpu_hardware_metrics'] = gpu_metrics

    # Write JSON
    with open(file_path, 'w') as f:
        json.dump(self.results[task_id], f, indent=2)
```

**Result JSON structure:**

```json
{
  "metadata": {
    "session_start_iso": "2026-02-01T14:30:45+0000",
    "model_name": "qwen3-vl:2b-instruct",
    "infrastructure_tag": "singleGPU"
  },
  "raw_events": [...],
  "computed_metrics": {
    "throughput_metrics": {
      "tokens_per_second": 42.5
    },
    "tool_confidence_metrics": {...}
  },
  "gpu_hardware_metrics": {
    "avg_gpu_util_pct": 87.3,
    "max_gpu_util_pct": 95.2,
    "peak_vram_mb": 4250,
    "avg_temp_c": 72.5,
    "total_energy_joules": 540.5,
    "total_energy_kwh": 0.00015
  }
}
```

---

### Component 5: CSV Aggregation (1 hour)

#### **Modify:** `scripts/collect_metrics.py`

**Extract GPU metrics from result JSONs:**

```python
def collect_metrics(result_json_path):
    """Parse result JSON and extract all metrics to CSV row."""

    with open(result_json_path, 'r') as f:
        result_data = json.load(f)

    # Existing metrics
    row = {
        'task_name': result_data['metadata']['task_name'],
        'model_name': result_data['metadata']['model_name'],
        'success': result_data['computed_metrics']['task_completion_status']['success'],
        # ... existing columns ...
    }

    # Throughput metrics
    throughput_metrics = result_data.get('computed_metrics', {}).get('throughput_metrics', {})
    row['tokens_per_second'] = throughput_metrics.get('tokens_per_second', '')

    # GPU hardware metrics
    gpu_metrics = result_data.get('gpu_hardware_metrics', {})
    row['avg_gpu_util_pct'] = gpu_metrics.get('avg_gpu_util_pct', '')
    row['max_gpu_util_pct'] = gpu_metrics.get('max_gpu_util_pct', '')
    row['avg_vram_mb'] = gpu_metrics.get('avg_vram_mb', '')
    row['peak_vram_mb'] = gpu_metrics.get('peak_vram_mb', '')
    row['avg_temp_c'] = gpu_metrics.get('avg_temp_c', '')
    row['max_temp_c'] = gpu_metrics.get('max_temp_c', '')
    row['avg_power_w'] = gpu_metrics.get('avg_power_w', '')
    row['total_energy_joules'] = gpu_metrics.get('total_energy_joules', '')
    row['total_energy_kwh'] = gpu_metrics.get('total_energy_kwh', '')

    # Tool confidence metrics
    confidence_metrics = result_data.get('computed_metrics', {}).get('tool_confidence_metrics', {})
    row['avg_tool_confidence'] = confidence_metrics.get('avg_tool_confidence', '')
    row['min_tool_confidence'] = confidence_metrics.get('min_tool_confidence', '')

    return row
```

---

### Component 6: Tool Call Confidence (2-3 hours)

#### **Modify:** `computer-use-demo/computer_use_demo/providers/openai_adapter.py`

**Step 1: Enable logprobs in API request**

```python
class OpenAIAdapter(BaseProviderAdapter):
    def prepare_request(self, transcript, tools, options):
        # ... existing code ...

        payload = {
            "model": options.model,
            "messages": messages_payload,
            "temperature": options.temperature,
            "max_tokens": options.max_output_tokens,

            # NEW: Enable logprobs
            "logprobs": True,
            "top_logprobs": 5  # Get top 5 alternative tokens
        }

        # ... rest of code ...
```

**Step 2: Add confidence extraction helper**

```python
import math

def _extract_tool_confidence(logprobs_data, tool_name):
    """
    Extract confidence score from logprobs for a tool call.

    Logprobs are in log space: logprob = log(probability)
    Convert to probability: prob = e^(logprob)

    Returns float between 0-1 (higher = more confident), or None if no data.
    """
    if not logprobs_data:
        return None

    # Parse logprobs structure (OpenAI format)
    # logprobs_data = {
    #   'content': [
    #     {'token': 'bash', 'logprob': -0.123, 'top_logprobs': [...]},
    #     ...
    #   ]
    # }

    token_probs = []

    content = logprobs_data.get('content', [])
    if not content:
        return None

    for token_data in content:
        logprob = token_data.get('logprob', None)
        if logprob is not None:
            # Convert log probability to probability
            # probability = e^(logprob)
            prob = math.exp(logprob)
            token_probs.append(prob)

    if not token_probs:
        return None

    # Use average probability as confidence score
    confidence = sum(token_probs) / len(token_probs)
    return round(confidence, 4)
```

**Step 3: Add confidence to tool calls**

```python
class OpenAIAdapter(BaseProviderAdapter):
    def parse_response(self, response):
        # ... existing code that extracts tool calls ...

        # Get logprobs from response
        logprobs = response.payload.get('logprobs', None)

        # When creating tool call segments:
        for call in tool_calls:
            function = call.get('function', {})
            tool_name = function.get('name', '')

            # Extract confidence
            confidence = _extract_tool_confidence(logprobs, tool_name)

            tool_segment = ToolCallSegment(
                tool_name=tool_name,
                arguments=arguments,
                call_id=call.get("id") or str(uuid4())
            )

            # Add confidence to metadata
            if confidence is not None:
                tool_segment.metadata['confidence'] = confidence

            segments.append(tool_segment)
```

**Step 4: Aggregate confidence metrics**

#### **Modify:** `computer-use-demo/computer_use_demo/loop.py`

```python
# In computed_metrics calculation section:

# Collect tool confidence scores from events
tool_confidences = []
for event in raw_events:
    if event['event'] == 'TOOL_CALL_START':
        confidence = event.get('data', {}).get('confidence')
        if confidence is not None:
            tool_confidences.append(confidence)

# Calculate aggregates
if tool_confidences:
    computed_metrics['tool_confidence_metrics'] = {
        'avg_tool_confidence': round(sum(tool_confidences) / len(tool_confidences), 4),
        'min_tool_confidence': round(min(tool_confidences), 4),
        'max_tool_confidence': round(max(tool_confidences), 4),
        'tool_calls_with_confidence': len(tool_confidences)
    }
else:
    # No confidence data available (Ollama doesn't support logprobs, or no tool calls)
    computed_metrics['tool_confidence_metrics'] = {
        'avg_tool_confidence': None,
        'min_tool_confidence': None,
        'max_tool_confidence': None,
        'tool_calls_with_confidence': 0
    }
```

**Result in events:**

```json
{
  "event": "TOOL_CALL_START",
  "timestamp": 1738012345.678,
  "data": {
    "tool_name": "bash",
    "arguments": {"command": "ls -la"},
    "confidence": 0.8752  // NEW: confidence score
  }
}
```

---

## Data Flow Architecture

### Overview

```
┌─────────────────────────────────────────────────┐
│  Task Execution (run_tasks_range.sh)           │
│  ├─ Start GPU monitor → gpu_metrics_*.csv      │
│  ├─ Run task → result_*.json                   │
│  └─ Stop GPU monitor                            │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  result_collector.py (PRIMARY STORAGE)          │
│  ├─ Parse gpu_metrics_*.csv                     │
│  ├─ Compute throughput                          │
│  ├─ Aggregate tool confidence                   │
│  └─ Save to result_*.json                       │
└─────────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────┐
│  collect_metrics.py (SECONDARY VIEW)            │
│  ├─ Read all result_*.json files                │
│  ├─ Extract all metrics                         │
│  └─ Export to results.csv                       │
└─────────────────────────────────────────────────┘
```

### File Organization

**Per-task outputs:**
```
logs_computer_use_eval/vscode_runs/
  qwen3-vl-2b_singleGPU_run_20260201_143000/
    task01_createFile_qwen3-vl-2b_singleGPU/
      ├─ gpu_metrics_task01_createFile.csv    # GPU monitoring data
      ├─ result_*.json                         # Primary storage (all metrics)
      └─ vscode_task01_createFile_evaluator.log
```

**Aggregated outputs:**
```
logs_computer_use_eval/
  vscode_runs/
    vscode_batch_summary.csv  # Task outcomes
    vscode_metrics.csv        # All metrics aggregated
```

---

## Files to Modify

### Summary

| File | Purpose | Effort |
|------|---------|--------|
| **NEW:** `scripts/monitor_gpu.py` | GPU monitoring background process | 2-3 hrs |
| `computer-use-demo/computer_use_demo/providers/openai_adapter.py` | Enable logprobs, extract confidence | 2-3 hrs |
| `computer-use-demo/computer_use_demo/loop.py` | Throughput, confidence aggregation | 1 hr |
| `scripts/run_tasks_range.sh` | Launch/kill GPU monitor | 1 hr |
| `PC-Canary/evaluator/core/result_collector.py` | Parse GPU CSV, add to result JSON | 1-2 hrs |
| `scripts/collect_metrics.py` | Extract new metrics to CSV | 1 hr |

### Detailed File Changes

#### 1. **NEW:** `/home/cc/MCPWorld/scripts/monitor_gpu.py`
- **Lines:** ~50 lines
- **Purpose:** Poll nvidia-smi every 1s, write timestamped CSV
- **Dependencies:** subprocess, time, csv, sys
- **Testing:** Run standalone for 10s, verify CSV output

#### 2. `/home/cc/MCPWorld/computer-use-demo/computer_use_demo/providers/openai_adapter.py`
- **Lines modified:** ~30 lines
- **Changes:**
  - `prepare_request()`: Add `logprobs: True` to payload
  - Add `_extract_tool_confidence()` helper function
  - `parse_response()`: Extract confidence, add to tool segment metadata
- **Testing:** Run task, verify logprobs in API response, confidence in events

#### 3. `/home/cc/MCPWorld/computer-use-demo/computer_use_demo/loop.py`
- **Lines modified:** ~40 lines
- **Changes:**
  - Add throughput calculation (tokens/sec)
  - Add tool confidence aggregation
  - Create `throughput_metrics` and `tool_confidence_metrics` dicts
- **Testing:** Run task, verify new metrics in result JSON

#### 4. `/home/cc/MCPWorld/scripts/run_tasks_range.sh`
- **Lines modified:** ~10 lines
- **Changes:**
  - Launch `monitor_gpu.py` before task
  - Capture PID, kill after task completes
  - Pass GPU log path
- **Testing:** Run single task, verify GPU CSV created and process cleaned up

#### 5. `/home/cc/MCPWorld/PC-Canary/evaluator/core/result_collector.py`
- **Lines modified:** ~50 lines
- **Changes:**
  - Add `_parse_gpu_metrics_csv()` function
  - Modify `save_results()` to include GPU metrics
  - Add `gpu_hardware_metrics` section to result JSON
- **Testing:** Run task, verify `gpu_hardware_metrics` in result JSON

#### 6. `/home/cc/MCPWorld/scripts/collect_metrics.py`
- **Lines modified:** ~20 lines
- **Changes:**
  - Extract throughput metrics from result JSON
  - Extract GPU metrics from result JSON
  - Extract tool confidence metrics from result JSON
  - Add columns to CSV output
- **Testing:** Run collect_metrics, verify new columns in results.csv

---

## Testing & Validation

### Test Plan

#### **Phase 1: Component Testing**

**Test 1.1: GPU Monitoring Script**
```bash
# Run standalone for 10 seconds
python3 scripts/monitor_gpu.py test_gpu.csv &
PID=$!
sleep 10
kill $PID

# Verify output
cat test_gpu.csv
# Expected: ~10 rows with timestamp, gpu_util_pct, vram_mb, temp_c, power_w
```

**Test 1.2: Throughput Calculations**
```bash
# Run single task
docker exec mcpworld bash -c "cd /workspace && ./scripts/run_tasks_range.sh vscode 1 1"

# Check result JSON
jq '.computed_metrics.throughput_metrics' logs_computer_use_eval/vscode_runs/.../result_*.json

# Expected:
# {
#   "tokens_per_second": 42.5
# }
```

**Test 1.3: Tool Confidence**
```bash
# Check raw events for confidence scores
jq '.raw_events[] | select(.event == "TOOL_CALL_START") | .data.confidence' result_*.json

# Expected: 0.xxxx values between 0-1

# Check aggregated metrics
jq '.computed_metrics.tool_confidence_metrics' result_*.json

# Expected:
# {
#   "avg_tool_confidence": 0.8234,
#   "min_tool_confidence": 0.4521,
#   "max_tool_confidence": 0.9811
# }
```

---

#### **Phase 2: Integration Testing**

**Test 2.1: GPU Metrics in Result JSON**
```bash
# Run task, verify GPU metrics added to result JSON
jq '.gpu_hardware_metrics' result_*.json

# Expected:
# {
#   "avg_gpu_util_pct": 87.3,
#   "max_gpu_util_pct": 95.2,
#   "peak_vram_mb": 4250,
#   "avg_temp_c": 72.5,
#   "total_energy_joules": 540.5,
#   "total_energy_kwh": 0.00015,
#   "sample_count": 247
# }
```

**Test 2.2: CSV Aggregation**
```bash
# Run collect_metrics
python3 scripts/collect_metrics.py

# Verify new columns in results.csv
head -n 1 results.csv | tr ',' '\n' | grep -E 'tokens_per_second|gpu_util|vram|energy|confidence'

# Expected columns:
# tokens_per_second
# avg_gpu_util_pct
# max_gpu_util_pct
# peak_vram_mb
# avg_temp_c
# total_energy_joules
# total_energy_kwh
# avg_tool_confidence
# min_tool_confidence
```

---

#### **Phase 3: End-to-End Validation**

**Test 3.1: Full Benchmark Run**
```bash
# Run all vscode tasks for one model
./scripts/run_multi_model_benchmark.sh vscode singleGPU

# Verify:
# 1. All tasks have gpu_metrics_*.csv
find logs_computer_use_eval -name "gpu_metrics_*.csv" | wc -l
# Expected: 25 (one per vscode task)

# 2. All result JSONs have gpu_hardware_metrics
find logs_computer_use_eval -name "result_*.json" -exec jq -e '.gpu_hardware_metrics' {} \; | wc -l
# Expected: 25

# 3. results.csv has all new columns
head -n 1 vscode_metrics.csv | tr ',' '\n' | wc -l
# Expected: >50 (original + new metrics)
```

**Test 3.2: Data Quality Validation**
```bash
# Verify GPU metrics are reasonable
jq '.gpu_hardware_metrics | {
  gpu_util: .avg_gpu_util_pct,
  vram: .peak_vram_mb,
  temp: .max_temp_c,
  energy: .total_energy_joules
}' result_*.json

# Sanity checks:
# ✓ GPU utilization: 0-100%
# ✓ VRAM: 2000-8000 MB for 2B model
# ✓ Temperature: 30-90°C
# ✓ Energy: >0 joules

# Verify throughput is positive
jq '.computed_metrics.throughput_metrics.tokens_per_second' result_*.json

# Sanity check:
# ✓ Tokens/sec: 10-100 (depends on model size and hardware)

# Verify tool confidence is 0-1
jq '.computed_metrics.tool_confidence_metrics | {avg, min}' result_*.json

# Sanity check:
# ✓ 0 ≤ confidence ≤ 1
```

**Test 3.3: Correlation Analysis**
```python
import pandas as pd

# Load results
df = pd.read_csv('vscode_metrics.csv')

# Verify energy correlates with duration
correlation = df['total_energy_joules'].corr(df['total_duration_seconds'])
assert correlation > 0.8, "Energy should correlate with duration"

# Verify low confidence correlates with failures
df['low_confidence'] = df['min_tool_confidence'] < 0.5
failure_rate_low_conf = df[df['low_confidence']]['success'].mean()
failure_rate_high_conf = df[~df['low_confidence']]['success'].mean()

print(f"Failure rate (low confidence): {1 - failure_rate_low_conf:.2%}")
print(f"Failure rate (high confidence): {1 - failure_rate_high_conf:.2%}")
# Expected: Lower confidence → higher failure rate
```

---

## Effort Estimate

### Breakdown

| Component | Time | Difficulty | Priority |
|-----------|------|------------|----------|
| GPU monitoring script | 2-3 hrs | Medium | High |
| Throughput calculations | 1 hr | Easy | High |
| Integration in run_tasks | 1 hr | Easy | High |
| GPU metrics aggregation | 2 hrs | Medium | High |
| Tool confidence (logprobs) | 2-3 hrs | Medium | Medium |
| CSV aggregation updates | 1 hr | Easy | High |
| Testing & validation | 1-2 hrs | Easy | High |
| **TOTAL** | **10-13 hrs** | **Medium** | |

### Implementation Order

**Day 1 (4-5 hours):**
1. Create GPU monitoring script (2-3 hrs)
2. Add throughput calculations (1 hr)
3. Test both components (1 hr)

**Day 2 (3-4 hours):**
4. Integrate GPU monitoring into run_tasks (1 hr)
5. Add GPU metrics to result JSON (2 hrs)
6. Test integration (1 hr)

**Day 3 (3-4 hours):**
7. Add tool confidence logprobs (2-3 hrs)
8. Update CSV aggregation (1 hr)
9. End-to-end validation (1 hr)

### Risk Factors

**Low Risk:**
- Throughput calculations (existing data, simple math)
- CSV aggregation (existing pattern, add columns)

**Medium Risk:**
- GPU monitoring (subprocess management, process cleanup)
- Tool confidence (logprobs format may vary by Ollama version)

**Mitigation:**
- Test GPU monitor standalone before integration
- Add error handling for logprobs parsing
- Graceful degradation if metrics unavailable

---

## Why These Metrics Matter

### Self-Hosting Exclusive Advantages

| Metric | API Provider | Self-Hosted | Advantage |
|--------|--------------|-------------|-----------|
| Energy consumption | ❌ | ✅ | True operational cost |
| GPU utilization | ❌ | ✅ | Hardware efficiency |
| VRAM usage | ❌ | ✅ | Memory optimization |
| Throughput (tokens/sec) | ❌ | ✅ | Inference speed |
| Tool call confidence | ❌ | ✅ | Uncertainty quantification |

### Analysis Possibilities

**1. Energy Efficiency Comparison**
```python
# Compare models by energy per successful task
df_success = df[df['success'] == True]
energy_efficiency = df_success.groupby('model_name').agg({
    'total_energy_joules': 'mean',
    'total_duration_seconds': 'mean'
})

# Find "sweet spot" - best success rate per joule
df.groupby('model_name').apply(
    lambda x: x['success'].mean() / x['total_energy_joules'].mean()
).sort_values(ascending=False)
```

**2. GPU Utilization Analysis**
```python
# Identify GPU bottlenecks
low_util = df[df['avg_gpu_util_pct'] < 50]
print(f"Tasks with <50% GPU util: {len(low_util)}")
# Implies bottleneck elsewhere (CPU, I/O, context switching)

# Optimal GPU usage
optimal = df[(df['avg_gpu_util_pct'] > 80) & (df['max_temp_c'] < 75)]
print(f"Tasks in optimal range: {len(optimal)}")
```

**3. Failure Prediction**
```python
# Predict failures from low tool confidence
from sklearn.linear_model import LogisticRegression

X = df[['min_tool_confidence', 'avg_tool_confidence']].fillna(0.5)
y = df['success']

model = LogisticRegression()
model.fit(X, y)

# Feature importance
print("Confidence impact on success:", model.coef_)

# Predict failure risk
df['failure_risk'] = 1 - model.predict_proba(X)[:, 1]
high_risk = df[df['failure_risk'] > 0.7]
```

**4. Cost Comparison: Self-Hosting vs API**
```python
# Calculate true cost per task
electricity_rate = 0.12  # $/kWh
gpu_amortization = 0.50  # $/hour (e.g., $2000 GPU / 4000 hours)

df['electricity_cost'] = df['total_energy_kwh'] * electricity_rate
df['hardware_cost'] = df['total_duration_seconds'] / 3600 * gpu_amortization
df['total_cost_self_hosted'] = df['electricity_cost'] + df['hardware_cost']

# Compare to API pricing
api_cost_per_token = 0.000003  # Example: $3/1M tokens
df['api_cost'] = df['total_tokens'] * api_cost_per_token

# ROI analysis
savings = df['api_cost'] - df['total_cost_self_hosted']
print(f"Average savings per task: ${savings.mean():.4f}")
print(f"Break-even point: {df['total_tokens'].median() / 1e6:.1f}M tokens")
```

---

## Future Roadmap

### Phase 2 Ideas (Not Implemented)

**1. KV Cache Monitoring**
- **What:** Track KV cache size growth over conversation
- **How:** Indirect measurement via VRAM growth, or Ollama instrumentation
- **Effort:** 8-10 hours (hard)
- **Value:** Optimize long conversations, identify memory leaks

**2. Per-Layer Profiling**
- **What:** Time spent in each transformer layer
- **How:** Requires Ollama source modification or external profiler
- **Effort:** 15-20 hours (very hard)
- **Value:** Identify slow layers, optimize model architecture

**3. Multi-GPU Load Balancing**
- **What:** Metrics for tensor parallelism efficiency
- **How:** Monitor multiple GPUs, measure communication overhead
- **Effort:** 6-8 hours (medium)
- **Value:** Optimize multi-GPU setups

**4. Thermal Throttling Detection**
- **What:** Identify when GPU slows due to heat
- **How:** Correlate temperature spikes with throughput drops
- **Effort:** 3-4 hours (medium)
- **Value:** Improve cooling, prevent performance degradation

**5. Cost Modeling Dashboard**
- **What:** Interactive visualization of $/task breakdown
- **How:** Jupyter notebook with plotly/dash
- **Effort:** 4-6 hours (medium)
- **Value:** Business case for self-hosting vs APIs

---

## Appendix

### Glossary

**Terms:**

- **Prefill:** Initial processing of the prompt to populate KV cache
- **Decode:** Generating output tokens one at a time
- **TTFT:** Time to first token (latency before first output)
- **Logprobs:** Log probabilities - model's confidence per token
- **VRAM:** Video RAM (GPU memory)
- **KV Cache:** Cached key-value pairs from attention mechanism

**Metrics:**

- **Throughput:** Tokens generated per second
- **Energy:** Joules = watts × seconds
- **Confidence:** e^(logprob) converted to 0-1 scale

### References

- [Ollama OpenAI Compatibility](https://docs.ollama.com/openai)
- [Ollama Logprobs Support](https://medium.com/@rafal.kedziorski/peek-inside-your-llm-building-a-token-probability-analyzer-with-ollamas-new-logprobs-f5d794671016)
- [NVIDIA-SMI Documentation](https://developer.nvidia.com/nvidia-system-management-interface)
- [OpenAI Logprobs Guide](https://cookbook.openai.com/examples/using_logprobs)

---

**Document Version:** 1.0
**Last Updated:** 2026-02-01
**Next Review:** After Phase 1 implementation
