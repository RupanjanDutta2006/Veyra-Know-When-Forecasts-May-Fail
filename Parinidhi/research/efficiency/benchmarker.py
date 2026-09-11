"""
Veyra Research — Track 8: Efficiency Benchmarker
Measures inference latency, calibration overhead, memory footprint, model size, and feature complexity.
"""
from __future__ import annotations
import os
import sys
import time
import tracemalloc
from typing import Dict, List, Any, Callable
import numpy as np


class EfficiencyBenchmarker:
    """
    Measures operational runtime performance metrics:
      - Inference Latency (Mean, p50, p95, p99)
      - Calibration Latency
      - Memory Footprint (Peak RAM in MB)
      - Feature Dimension Count
      - Model Serialization Footprint (KB on disk)
    """

    @staticmethod
    def benchmark_inference_latency(predict_fn: Callable[[Dict[str, Any]], Any],
                                    sample_input: Dict[str, Any],
                                    n_warmup: int = 50,
                                    n_iterations: int = 500) -> Dict[str, float]:
        """
        Microbenchmarks single-instance inference latency.
        """
        # Warmup
        for _ in range(n_warmup):
            _ = predict_fn(sample_input)

        latencies_ms = []
        for _ in range(n_iterations):
            t0 = time.perf_counter()
            _ = predict_fn(sample_input)
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

        lat_arr = np.array(latencies_ms)
        return {
            "latency_mean_ms": float(np.mean(lat_arr)),
            "latency_p50_ms": float(np.percentile(lat_arr, 50)),
            "latency_p95_ms": float(np.percentile(lat_arr, 95)),
            "latency_p99_ms": float(np.percentile(lat_arr, 99)),
            "throughput_instances_per_sec": float(1000.0 / np.mean(lat_arr)) if np.mean(lat_arr) > 0 else np.nan
        }

    @staticmethod
    def benchmark_memory_footprint(workload_fn: Callable[[], Any]) -> Dict[str, float]:
        """
        Measures peak memory allocation during workload execution using tracemalloc.
        """
        tracemalloc.start()
        t0 = time.perf_counter()
        _ = workload_fn()
        elapsed = time.perf_counter() - t0
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        return {
            "current_memory_kb": round(current / 1024.0, 2),
            "peak_memory_kb": round(peak / 1024.0, 2),
            "peak_memory_mb": round(peak / (1024.0 * 1024.0), 3),
            "elapsed_seconds": round(elapsed, 4)
        }

    @staticmethod
    def measure_artifact_size(file_path: str) -> Dict[str, Any]:
        """
        Measures file size on disk in Bytes, KB, and MB.
        """
        if not os.path.exists(file_path):
            return {"exists": False, "size_bytes": 0, "size_kb": 0.0, "size_mb": 0.0}

        size_b = os.path.getsize(file_path)
        return {
            "exists": True,
            "size_bytes": size_b,
            "size_kb": round(size_b / 1024.0, 2),
            "size_mb": round(size_b / (1024.0 * 1024.0), 3)
        }
