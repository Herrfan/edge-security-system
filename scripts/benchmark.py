"""Phase 8 — 本机性能基准。

跑 demo_e2e 同时采样 RSS / CPU / Ollama 模型体积 / 磁盘占用。
输出 JSON 报告，只记录实际测得的数值。未测量的指标明确标记
"待验证"（不伪造）。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def probe_models() -> dict:
    """Ollama pull 下来的模型体积 (best-effort)."""
    out: dict = {"ollama_models": [], "llm_model_size_bytes": None, "embedding_model_size_bytes": None}
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if r.status_code == 200:
            models = r.json().get("models", [])
            out["ollama_models"] = [
                {"name": m["name"], "size_bytes": m.get("size")} for m in models
            ]
            for m in models:
                if m["name"].startswith("qwen2.5:3b") or m["name"].startswith("qwen2.5"):
                    out["llm_model_size_bytes"] = m.get("size")
                if "nomic-embed-text" in m["name"]:
                    out["embedding_model_size_bytes"] = m.get("size")
    except Exception as e:
        out["ollama_error"] = str(e)
    return out


def probe_process() -> dict:
    out: dict = {"rss_bytes": None, "cpu_percent": None, "psutil_available": False}
    try:
        import psutil
        out["psutil_available"] = True
        # Run dummy load to make CPU measurable
        p = psutil.Process()
        p.cpu_percent(interval=None)  # prime
        t0 = time.perf_counter()
        _ = sum(range(10_000_000))
        t1 = time.perf_counter()
        out["cpu_percent"] = p.cpu_percent(interval=None)
        out["rss_bytes"] = p.memory_info().rss
        out["cpu_burn_ms"] = (t1 - t0) * 1000
    except ImportError:
        pass
    return out


def probe_disk() -> dict:
    out: dict = {}
    try:
        import shutil
        u = shutil.disk_usage(str(REPO_ROOT))
        out["repo_disk_total_bytes"] = u.total
        out["repo_disk_used_bytes"] = u.used
        out["repo_disk_free_bytes"] = u.free
    except Exception as e:
        out["disk_error"] = str(e)
    # Ollama models dir size
    try:
        ollama_dirs = [
            Path.home() / ".ollama",
            Path.home() / ".ollama" / "models",
        ]
        total = 0
        for d in ollama_dirs:
            if d.exists():
                for f in d.rglob("*"):
                    if f.is_file():
                        try:
                            total += f.stat().st_size
                        except Exception:
                            pass
        out["ollama_dir_bytes"] = total if total else None
    except Exception as e:
        out["ollama_dir_error"] = str(e)
    return out


def main() -> int:
    print("[bench] Probing system...")
    models = probe_models()
    proc = probe_process()
    disk = probe_disk()

    print("[bench] Running demo_e2e to measure true end-to-end latency...")
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "demo_e2e.py"), "--steps", "5"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=180,
    )
    t1 = time.perf_counter()
    wall_ms = (t1 - t0) * 1000

    report_path = REPO_ROOT / "data" / "demo_report.json"
    demo_data: dict = {}
    if report_path.exists():
        demo_data = json.loads(report_path.read_text(encoding="utf-8"))

    bench = {
        "environment": demo_data.get("environment", {}),
        "wall_clock_ms": wall_ms,
        "process": proc,
        "models": models,
        "disk": disk,
        "demo_summary": demo_data.get("summary", {}),
        "demo_steps": [
            {"name": s["name"], "ok": s["ok"], "duration_ms": s["duration_ms"]}
            for s in demo_data.get("steps", [])
        ],
        # ---- Not measured on this machine — task book requires 待验证 ----
        "not_measured": {
            "edge_device_latency": "待验证 (当前仅在开发机本地跑，未上目标边缘设备)",
            "gunicorn_throughput_rps": "待验证 (未做并发压测)",
            "model_inference_gpu_ms": "待验证 (本机无 GPU，仅 CPU)",
        },
    }

    out_path = REPO_ROOT / "data" / "benchmark_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(bench, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print("=" * 60)
    print("  BENCHMARK")
    print("=" * 60)
    print(f"  wall_clock_ms (end-to-end, incl import) : {wall_ms:.0f}")
    print(f"  psutil RSS (self)                       : {proc['rss_bytes']}")
    print(f"  Ollama models                           : {models['ollama_models']}")
    print(f"  Ollama dir bytes                        : {disk.get('ollama_dir_bytes')}")
    print("=" * 60)
    print(f"[bench] report → {out_path}")
    return 0 if result.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
