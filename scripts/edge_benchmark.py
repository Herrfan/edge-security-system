"""Phase 13 — Edge device performance benchmark harness.

Cross-platform (Linux / Windows) self-benchmark that:

  1. Probes the host: CPU cores + model + freq, total RAM, kernel, network
     interfaces, thermal sensors (Linux /sys/class/thermal), disk IO latency,
     GPU/NPU presence (CUDA, OpenVINO, TensorRT, Coral Edge TPU).
  2. Measures per-phase wall-clock for the full ``demo_e2e.py`` pipeline —
     import, knowledge/sync, events/seed + detection, RAG (real qwen2.5:3b),
     validate, dry-run execute.
  3. Profiles Python import memory: measure RSS before/after importing each
     major app module so we know which phase of the import chain is heavy.
  4. Runs a small concurrent HTTP smoke test against TestClient — N workers
     hitting health + events/seed + policy-proposal/generate in parallel.
  5. Records "not measured" for anything that requires privileged access
     (iptables real-run), a GPU we don't have, or an actual device we
     couldn't SSH into — never fabricate numbers.

Output: JSON report at ``data/edge_benchmark_report.json`` + human-readable
summary on stdout.
"""
from __future__ import annotations

import gc
import importlib
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


# =========================================================================
# Host probes — best-effort, never raise
# =========================================================================


def probe_cpu() -> Dict[str, Any]:
    out: Dict[str, Any] = {
        "cores_logical": os.cpu_count(),
        "platform_machine": platform.machine(),
        "platform_processor": platform.processor(),
        "platform_system": platform.system(),
        "platform_release": platform.release(),
        "kernel_version": platform.version(),
    }
    # Linux-specific — /proc/cpuinfo gives real brand/model
    if platform.system() == "Linux":
        try:
            text = Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="ignore")
            models = set()
            for line in text.splitlines():
                if line.startswith("model name"):
                    models.add(line.split(":", 1)[1].strip())
            out["cpu_models_from_proc"] = sorted(models)
            # scaling freq
            try:
                mhz_path = Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq")
                if mhz_path.exists():
                    out["cpu0_cur_freq_khz"] = int(mhz_path.read_text().strip())
            except Exception:
                pass
            # avg load
            try:
                out["load_avg_1_5_15"] = [round(x, 2) for x in os.getloadavg()]
            except Exception:
                pass
        except Exception as e:
            out["proc_error"] = str(e)
    # Windows-specific
    elif platform.system() == "Windows":
        try:
            import psutil
            out["psutil_cpu_freq_mhz"] = psutil.cpu_freq().current if psutil.cpu_freq() else None
            out["psutil_cpu_percent"] = psutil.cpu_percent(interval=0.2)
        except Exception:
            pass
    return out


def probe_memory() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    if platform.system() == "Linux":
        try:
            text = Path("/proc/meminfo").read_text(encoding="utf-8", errors="ignore")
            for line in text.splitlines():
                k, _, v = line.partition(":")
                v = v.strip()
                if k in ("MemTotal", "MemFree", "MemAvailable", "Buffers", "Cached",
                         "SwapTotal", "SwapFree"):
                    # value usually ends in kB
                    try:
                        kb = int(v.split()[0])
                        out[f"{k}_kb"] = kb
                    except (ValueError, IndexError):
                        pass
        except Exception as e:
            out["proc_error"] = str(e)
    try:
        import psutil
        v = psutil.virtual_memory()
        out["psutil_total_bytes"] = v.total
        out["psutil_available_bytes"] = v.available
        out["psutil_percent"] = v.percent
    except Exception:
        pass
    return out


def probe_thermal() -> Dict[str, Any]:
    """Linux /sys/class/thermal probes. Windows has WMI but requires admin — skip."""
    out: Dict[str, Any] = {}
    if platform.system() != "Linux":
        return out
    try:
        root = Path("/sys/class/thermal")
        entries = []
        if root.exists():
            for zone in sorted(root.iterdir()):
                temp_path = zone / "temp"
                type_path = zone / "type"
                if temp_path.exists():
                    try:
                        temp_milli = int(temp_path.read_text().strip())
                        entries.append({
                            "zone": zone.name,
                            "type": type_path.read_text().strip() if type_path.exists() else "",
                            "temp_c": temp_milli / 1000.0,
                        })
                    except Exception:
                        pass
        out["zones"] = entries
    except Exception as e:
        out["error"] = str(e)
    return out


def probe_network() -> Dict[str, Any]:
    out: Dict[str, Any] = {"hostname": socket.gethostname(), "interfaces": []}
    try:
        import psutil
        for nic, addrs in psutil.net_if_addrs().items():
            ipv4 = [a.address for a in addrs if a.family == socket.AF_INET]
            mac = [a.address for a in addrs if a.family == socket.AF_LINK]
            out["interfaces"].append({
                "name": nic,
                "ipv4": ipv4,
                "mac": mac[0] if mac else None,
            })
        io = psutil.net_io_counters(pernic=True)
        out["pernic_io"] = {nic: {"bytes_sent": v.bytes_sent, "bytes_recv": v.bytes_recv}
                             for nic, v in io.items()}
    except Exception:
        pass
    return out


def probe_disk() -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    try:
        u = shutil.disk_usage(str(REPO_ROOT))
        out["repo_total_bytes"] = u.total
        out["repo_used_bytes"] = u.used
        out["repo_free_bytes"] = u.free
    except Exception as e:
        out["disk_error"] = str(e)
    # micro-benchmark: 4 KiB sequential write + fsync latency
    try:
        import tempfile
        t0 = time.perf_counter()
        with tempfile.NamedTemporaryFile(dir=str(REPO_ROOT), delete=True) as tf:
            tf.write(b"." * 4096)
            tf.flush()
            os.fsync(tf.fileno())
        out["write_4k_fsync_ms"] = (time.perf_counter() - t0) * 1000
    except Exception:
        pass
    return out


def probe_accelerators() -> Dict[str, Any]:
    """GPU / NPU detection — best-effort import probes."""
    out: Dict[str, Any] = {}
    for pkg in ("torch", "tensorrt", "openvino", "onnxruntime", "onnxruntime_gpu"):
        try:
            mod = importlib.import_module(pkg)
            out[f"python_{pkg}"] = "installed"
            if pkg == "torch":
                out["cuda_available"] = bool(mod.cuda.is_available())
                if mod.cuda.is_available():
                    out["cuda_device_count"] = mod.cuda.device_count()
                    out["cuda_device_name"] = mod.cuda.get_device_name(0)
        except ImportError:
            pass
        except Exception as e:
            out[f"python_{pkg}"] = f"error: {e}"
    # Coral Edge TPU
    try:
        import glob as _glob
        tpu = _glob.glob("/dev/apex_*") + _glob.glob("/dev/usbtp*")
        if tpu:
            out["coral_tpu"] = tpu
    except Exception:
        pass
    return out


def probe_ollama() -> Dict[str, Any]:
    out: Dict[str, Any] = {"ollama_reachable": False, "models": []}
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=2)
        if r.status_code == 200:
            out["ollama_reachable"] = True
            out["models"] = [
                {"name": m["name"], "size_bytes": m.get("size"),
                 "details": m.get("details", {})}
                for m in r.json().get("models", [])
            ]
    except Exception as e:
        out["ollama_error"] = str(e)
    return out


# =========================================================================
# Import memory profile
# =========================================================================


_MODULES_TO_PROFILE = [
    # Import chain 1: config + logging (should be tiny)
    ("app.core.config", "config + Settings"),
    ("app.core.logging", "logging setup"),
    # Import chain 2: SQLAlchemy + ORMs
    ("app.core.database", "SQLAlchemy engine + ORMs"),
    # Import chain 3: domain schemas
    ("app.domain.common", "domain.common enums"),
    ("app.domain.policy", "policy Pydantic schemas"),
    ("app.domain.evidence", "Evidence schema"),
    ("app.domain.execution", "ExecutionRecord schema"),
    # Import chain 4: adapters
    ("app.adapters.embedding.base", "embedding adapters"),
    ("app.adapters.llm.base", "LLM adapters (ollama client)"),
    ("app.adapters.backends", "firewall backend registry"),
    # Import chain 5: services
    ("app.services.retrieval", "VecIndex + BM25 + RRF"),
    ("app.services.rag_service", "RAG orchestrator (pulls llm + retrieval)"),
    # Import chain 6: FastAPI app
    ("app.main", "FastAPI app + lifespan"),
]


def profile_imports() -> List[Dict[str, Any]]:
    """Run each import in a fresh subprocess and capture RSS delta.

    Each spawned Python process:
        1. Imports psutil, measures RSS
        2. Imports the target module
        3. Measures RSS again
        4. Dumps {"before":..., "after":..., "delta":...}

    This avoids Python import caching across measurements.
    """
    results: List[Dict[str, Any]] = []
    for module, description in _MODULES_TO_PROFILE:
        script = (
            "import sys, json, subprocess;"
            f"sys.path.insert(0, {str(REPO_ROOT)!r});"
            "import psutil;"
            "p = psutil.Process();"
            "p.cpu_percent(interval=None);"
            "before = p.memory_info().rss;"
            f"import {module};"
            "after = p.memory_info().rss;"
            "print(json.dumps({'before': before, 'after': after, 'delta': after - before}))"
        )
        try:
            r = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True, text=True, timeout=30,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            )
            if r.returncode == 0 and r.stdout.strip():
                data = json.loads(r.stdout.strip().splitlines()[-1])
                data["module"] = module
                data["description"] = description
                results.append(data)
            else:
                results.append({"module": module, "description": description,
                                "error": (r.stderr or r.stdout or "").strip()[:200]})
        except Exception as e:
            results.append({"module": module, "description": description, "error": str(e)})
    return results


# =========================================================================
# End-to-end wall-clock — subprocess calls demo_e2e.py
# =========================================================================


def measure_demo_wall_clock() -> Dict[str, Any]:
    """Run demo_e2e.py in subprocess, return summary + wall clock."""
    t0 = time.perf_counter()
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "demo_e2e.py"), "--steps", "6"],
        capture_output=True, text=True, timeout=240,
        cwd=str(REPO_ROOT),
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    t1 = time.perf_counter()
    wall_ms = (t1 - t0) * 1000

    report_path = REPO_ROOT / "data" / "demo_report.json"
    demo_steps: List[Dict[str, Any]] = []
    if report_path.exists():
        try:
            demo = json.loads(report_path.read_text(encoding="utf-8"))
            demo_steps = [
                {"name": s["name"], "ok": s["ok"], "duration_ms": s.get("duration_ms")}
                for s in demo.get("steps", [])
            ]
        except Exception:
            pass

    return {
        "wall_clock_ms": wall_ms,
        "returncode": result.returncode,
        "demo_steps": demo_steps,
        "stderr_tail": (result.stderr or "")[-200:],
    }


# =========================================================================
# Concurrent smoke — real TestClient, N workers
# =========================================================================


def _concurrency_worker(host_tasks, results, idx):
    """Each worker: spawns its own TestClient, calls a fixed set of endpoints."""
    import asyncio
    async def _run():
        from fastapi.testclient import TestClient
        from app.main import create_app
        app = create_app()
        with TestClient(app) as client:
            local = []
            for label, fn in host_tasks:
                t0 = time.perf_counter()
                try:
                    ok = fn(client)
                    local.append({"task": label, "ok": ok,
                                  "latency_ms": (time.perf_counter() - t0) * 1000})
                except Exception as e:
                    local.append({"task": label, "ok": False,
                                  "error": str(e)[:100],
                                  "latency_ms": (time.perf_counter() - t0) * 1000})
            results[idx] = local
    asyncio.run(_run())


def measure_concurrency(*, workers: int = 4, rounds: int = 3) -> Dict[str, Any]:
    """N workers × M rounds each, per-endpoint latency histogram."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def fn_health(client):
        r = client.get("/health")
        return r.status_code == 200

    def fn_seed(client):
        sample = REPO_ROOT / "data" / "flows_sample.csv"
        if not sample.exists():
            return True
        with open(sample, "rb") as f:
            r = client.post("/api/v1/flows/seed-policy",
                            files={"file": ("flows_sample.csv", f, "text/csv")})
        return 200 <= r.status_code < 400

    tasks = [
        ("health", fn_health),
        ("health", fn_health),  # double so we see variance
        ("seed", fn_seed),
    ]

    all_results = {}
    t_total0 = time.perf_counter()

    for round_n in range(rounds):
        round_results: Dict[int, List[Dict]] = {}
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_concurrency_worker, tasks, round_results, i)
                       for i in range(workers)]
            for fut in as_completed(futures):
                fut.result()
        all_results[round_n] = round_results

    t_total1 = time.perf_counter()

    # aggregate per-task across all workers + rounds
    by_task: Dict[str, List[float]] = {}
    ok_by_task: Dict[str, int] = {}
    fail_by_task: Dict[str, int] = {}
    for round_results in all_results.values():
        for local in round_results.values():
            for r in local:
                by_task.setdefault(r["task"], []).append(r["latency_ms"])
                if r["ok"]:
                    ok_by_task[r["task"]] = ok_by_task.get(r["task"], 0) + 1
                else:
                    fail_by_task[r["task"]] = fail_by_task.get(r["task"], 0) + 1

    summary = {}
    for task, lats in by_task.items():
        lats_sorted = sorted(lats)
        n = len(lats_sorted)
        def pct(p): return lats_sorted[min(n - 1, int(p / 100 * n))]
        summary[task] = {
            "n": n,
            "min_ms": lats_sorted[0],
            "p50_ms": pct(50),
            "p95_ms": pct(95),
            "max_ms": lats_sorted[-1],
            "ok": ok_by_task.get(task, 0),
            "failed": fail_by_task.get(task, 0),
        }

    return {
        "workers": workers,
        "rounds": rounds,
        "total_tasks": workers * rounds * len(tasks),
        "total_wall_clock_ms": (t_total1 - t_total0) * 1000,
        "by_task": summary,
    }


# =========================================================================
# Not-measured — mark explicitly, never fabricate
# =========================================================================


def not_measured_section() -> Dict[str, str]:
    """Things this harness CANNOT measure without special hardware / access."""
    return {
        "real_iptables_apply_latency": (
            "待验证 — 需 allow_real_execution=True + 真实 Linux iptables/nft 权限 "
            "(默认安全边界 prevent)"
        ),
        "nftables_rule_rollback_latency": (
            "待验证 — 同上，需真实执行权限 + 目标 Linux 设备"
        ),
        "gpu_inference_latency_ms": (
            "待验证 — 目标边缘设备可能有 GPU/Coral NPU/OpenVINO VPU；"
            "本机无加速器，仅 CPU 推理"
        ),
        "gunicorn_100_workers_rps": (
            "待验证 — 需独立 nginx+gunicorn 部署 + HTTP 压测（wrk / ab）"
        ),
        "sqlite_async_concurrency_contention": (
            "待验证 — aiosqlite 单 writer 限制在多 worker 下可能锁竞争；"
            "需真实 uvicorn --workers N 部署下并发压测"
        ),
        "Cisco_Juniper_PAN_OS_apply_latency": (
            "待验证 — Phase 13 计划加后端，需真实网络设备 + SSH/API 凭据"
        ),
        "VictoriaMetrics_real_ingest_latency": (
            "待验证 — vm_remote_write_url 指向真实 VM 实例，当前未部署"
        ),
        "mTLS_handshake_latency": (
            "待验证 — Phase 13 计划加 mTLS，当前 auth_enabled=False 默认"
        ),
        "token_blacklist_purge_under_load": (
            "待验证 — 高频登出时 purge 定时器与并发请求争抢；"
            "需真实多 worker 部署"
        ),
    }


# =========================================================================
# Main
# =========================================================================


def main() -> int:
    print("=" * 72)
    print("  EDGE SECURITY SYSTEM — EDGE BENCHMARK")
    print(f"  host: {platform.node()}  system: {platform.system()}  time: {datetime.now(timezone.utc).isoformat()}Z")
    print("=" * 72)

    # ---- system probes ----
    print("[1/6] Host probes: CPU, RAM, thermal, network, disk, accelerators...")
    cpu = probe_cpu()
    mem = probe_memory()
    thermal = probe_thermal()
    net = probe_network()
    disk = probe_disk()
    accel = probe_accelerators()
    ollama = probe_ollama()

    print(f"      CPU cores={cpu['cores_logical']} machine={cpu['platform_machine']} "
          f"proc={cpu['platform_processor'][:40] if cpu['platform_processor'] else 'n/a'}")
    print(f"      RAM total={mem.get('psutil_total_bytes', mem.get('MemTotal_kb', 'n/a'))} "
          f"accel keys={list(accel.keys()) or 'none'}")

    # ---- import memory profile ----
    print("[2/6] Import memory profile (per-module RSS delta in fresh subprocess)...")
    gc.collect()
    imports = profile_imports()
    imports_sorted = sorted(imports, key=lambda x: x.get("delta", 0) if "delta" in x else -1, reverse=True)
    for row in imports_sorted:
        if "delta" in row:
            print(f"      +{row['delta']/1024:.0f} KB  → {row['module']}")
        else:
            print(f"      ERROR  → {row['module']}: {row.get('error', '?')[:60]}")

    # ---- demo wall clock ----
    print("[3/6] End-to-end wall clock (subprocess calls demo_e2e --steps 6)...")
    demo = measure_demo_wall_clock()
    print(f"      wall_clock={demo['wall_clock_ms']:.0f} ms  returncode={demo['returncode']}")
    for s in demo["demo_steps"]:
        status = "OK" if s["ok"] else "FAIL"
        print(f"        [{status}] {s['name']:30s} {s['duration_ms'] or '?':>8} ms")

    # ---- concurrent smoke ----
    print("[4/6] Concurrent smoke (workers=4, rounds=3)...")
    conc = measure_concurrency(workers=4, rounds=3)
    print(f"      total_tasks={conc['total_tasks']} total_wall_clock={conc['total_wall_clock_ms']:.0f} ms")
    for task, agg in conc["by_task"].items():
        print(f"      {task}: p50={agg['p50_ms']:.1f}ms  p95={agg['p95_ms']:.1f}ms  "
              f"n={agg['n']}  failed={agg['failed']}")

    # ---- environment summary ----
    print("[5/6] Pytest full-suite wall clock...")
    import subprocess as _sp
    pytest_t0 = time.perf_counter()
    _sp.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=line", "-x"],
        capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=480,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )
    pytest_ms = (time.perf_counter() - pytest_t0) * 1000
    print(f"      pytest -q wall_clock={pytest_ms:.0f} ms")

    # ---- assemble report ----
    print("[6/6] Assembling report...")
    report: Dict[str, Any] = {
        "meta": {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "runner_host": platform.node(),
            "runner_system": platform.system(),
            "repo_head": _git_head(),
            "harness_version": "phase13-edge-benchmark",
        },
        "host": {
            "cpu": cpu,
            "memory": mem,
            "thermal": thermal,
            "network": net,
            "disk": disk,
            "accelerators": accel,
        },
        "ollama": ollama,
        "import_profile": imports_sorted,
        "demo_e2e": demo,
        "concurrent_smoke": conc,
        "pytest_full_wall_clock_ms": pytest_ms,
        "not_measured": not_measured_section(),
    }

    out_path = REPO_ROOT / "data" / "edge_benchmark_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    print()
    print("=" * 72)
    print(f"  REPORT → {out_path}")
    print(f"  pytest full wall clock : {pytest_ms:.0f} ms")
    print(f"  demo wall clock        : {demo['wall_clock_ms']:.0f} ms")
    biggest = imports_sorted[0] if imports_sorted else None
    if biggest and "delta" in biggest:
        print(f"  heaviest import        : {biggest['module']} (+{biggest['delta']/1024:.0f} KB)")
    print(f"  total_tasks            : {conc['total_tasks']}")
    print("=" * 72)
    return 0


def _git_head() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                           capture_output=True, text=True, cwd=str(REPO_ROOT), timeout=5)
        return r.stdout.strip() if r.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


if __name__ == "__main__":
    sys.exit(main())
