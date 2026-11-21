"""Opt-in end-to-end upload benchmark; uses an inert engine, never WinDivert.

    .venv\\Scripts\\python.exe tools\\benchmark_profile_streaming.py --size-mib 1024
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import threading
import time
import tracemalloc

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

import psutil
import bypass_service as client
from tests.test_bypass_service import ServiceIntegrationTests


def benchmark(size_mib: int) -> dict:
    size = size_mib * 1024 * 1024
    fixture = None
    ServiceIntegrationTests.setUpClass()
    try:
        fixture = ServiceIntegrationTests("test_large_streamed_list_has_bounded_memory_and_exact_contents")
        fixture.setUp()
        if shutil.disk_usage(fixture.root).free < 2 * size + 128 * 1024 * 1024:
            raise RuntimeError("Not enough temporary disk space for source + staged file")
        source = fixture.root / "benchmark-hosts.txt"
        # Synthetic but nontrivial domains; the repeated blocks make this a
        # transport benchmark, NOT an estimate of winws's domain-index memory.
        block = b"".join(f"host-{index:08d}.example.test\n".encode() for index in range(8192))
        block = block[:client.BLOCK_BYTES]
        expected_hash = hashlib.sha256()
        remaining = size
        with source.open("wb") as stream:
            while remaining:
                part = block[:remaining]
                stream.write(part)
                expected_hash.update(part)
                remaining -= len(part)

        wire_bytes = 0
        original_write = fixture.pipe._write

        def count_write(data):
            nonlocal wire_bytes
            wire_bytes += len(data)
            original_write(data)

        fixture.pipe._write = count_write
        gui, service = psutil.Process(), psutil.Process(fixture.host.pid)
        baseline = [gui.memory_info().rss, service.memory_info().rss]
        peaks = baseline.copy()
        stopped = threading.Event()

        def sample():
            while not stopped.wait(0.02):
                for index, process in enumerate((gui, service)):
                    peaks[index] = max(peaks[index], process.memory_info().rss)

        sampler = threading.Thread(target=sample, daemon=True)
        sampler.start()
        tracemalloc.start()
        try:
            started = time.perf_counter()
            request = client.profile_request(subprocess.list2cmdline([
                str(fixture.root / "winws.exe"), "--hostlist=" + str(source),
            ]), fixture.root)
            result = fixture.pipe.request(request)
            elapsed = time.perf_counter() - started
            _, python_peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
            stopped.set()
            sampler.join()

        staged = Path(result["log"].split("arg=--hostlist=")[1].splitlines()[0])
        actual_hash = hashlib.sha256()
        with staged.open("rb") as stream:
            for part in iter(lambda: stream.read(client.BLOCK_BYTES), b""):
                actual_hash.update(part)
        if actual_hash.digest() != expected_hash.digest():
            raise AssertionError("Staged file differs from source")
        mib = 1024 * 1024
        return {
            "source_mib": size_mib,
            "wire_mib": round(wire_bytes / mib, 2),
            "seconds_including_fake_engine_start": round(elapsed, 3),
            "throughput_mib_s": round(size_mib / elapsed, 2),
            "peak_python_allocations_mib": round(python_peak / mib, 2),
            "gui_rss_increase_mib": round((peaks[0] - baseline[0]) / mib, 2),
            "service_rss_increase_mib": round((peaks[1] - baseline[1]) / mib, 2),
            "sha256_verified": True,
            "engine": "inert test executable; not real winws",
        }
    finally:
        if fixture is not None:
            fixture.tearDown()
        ServiceIntegrationTests.tearDownClass()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size-mib", type=int, default=128)
    args = parser.parse_args()
    if not 1 <= args.size_mib <= client.MAX_PROFILE_BYTES // (1024 * 1024):
        parser.error("--size-mib must be between 1 and 8192")
    print(json.dumps(benchmark(args.size_mib), indent=2))
