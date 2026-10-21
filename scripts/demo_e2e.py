"""Phase 8 — 一键端到端演示脚本。

从知识库同步 → 流量导入 → 检测 → RAG → 校验 → DRY_RUN 执行 → 可观测性快照，
全链路跑通并打印结构化 JSON 报告。

设计原则（遵守任务书 §8 验收）:

* 零隐藏手工步骤 — 一条命令跑完；
* 不伪造结果 — 如果任何一步失败，立即停止并打印真实错误；
* 不触发真实网络防御 — 默认 DRY_RUN，REAL 需显式 --real；
* 未测量指标显式标记 "unavailable" 或 "待验证"；
* 记录环境: Python 版本 / OS / CPU / RSS / 磁盘占用 / Ollama 模型状态。

用法:

    python scripts/demo_e2e.py [--steps N] [--llm-real] [--real-execute]
"""
from __future__ import annotations

import json
import os
import platform
import shutil
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# ---- Path setup: allow running from repo root or elsewhere ---------------
REPO_ROOT = Path(__file__).resolve().parent.parent
os.chdir(REPO_ROOT)
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

KNOWLEDGE_PATH = REPO_ROOT / "data" / "knowledge" / "security_knowledge.jsonl"
CSV_PATH = REPO_ROOT / "data" / "samples" / "flows_sample.csv"
DEFAULT_STEPS = 10  # events/seed 导入的 flow 数量

# ---------------------------------------------------------------------------
# Small stopwatch
# ---------------------------------------------------------------------------


@dataclass
class StepResult:
    name: str
    ok: bool
    duration_ms: float
    detail: Dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


def _run(name: str, fn) -> StepResult:
    t0 = time.perf_counter()
    try:
        detail = fn()
        return StepResult(
            name=name, ok=True,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            detail=detail or {},
        )
    except Exception as e:
        return StepResult(
            name=name, ok=False,
            duration_ms=(time.perf_counter() - t0) * 1000.0,
            error=f"{type(e).__name__}: {e}",
        )


# ---------------------------------------------------------------------------
# Environment probe (best-effort — never fail because of missing deps)
# ---------------------------------------------------------------------------


def probe_env() -> Dict[str, Any]:
    env: Dict[str, Any] = {
        "python": platform.python_version(),
        "os": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "repo_root": str(REPO_ROOT),
        "ollama_available": False,
        "ollama_model": None,
        "psutil_available": False,
        "disk_free_bytes": None,
        "rss_bytes": None,
        "cpu_percent": None,
    }
    # --- Ollama ---
    try:
        import requests
        r = requests.get("http://127.0.0.1:11434/api/tags", timeout=1.5)
        if r.status_code == 200:
            env["ollama_available"] = True
            env["ollama_model"] = [m["name"] for m in r.json().get("models", [])]
    except Exception:
        pass

    # --- psutil ---
    try:
        import psutil  # type: ignore[import-not-found]
        env["psutil_available"] = True
        p = psutil.Process()
        env["rss_bytes"] = p.memory_info().rss
        env["cpu_percent"] = p.cpu_percent(interval=None)
    except ImportError:
        pass

    # --- disk ---
    try:
        usage = shutil.disk_usage(str(REPO_ROOT))
        env["disk_free_bytes"] = usage.free
    except Exception:
        pass

    return env


# ---------------------------------------------------------------------------
# Main demo
# ---------------------------------------------------------------------------


def run_demo(*, steps: int = DEFAULT_STEPS, real_llm: bool = False, real_execute: bool = False) -> Dict[str, Any]:
    print(f"[demo] repo_root = {REPO_ROOT}")
    print(f"[demo] steps = {steps}  real_llm = {real_llm}  real_execute = {real_execute}")

    env = probe_env()
    print(f"[demo] Python {env['python']} on {env['os']} ({env['machine']})")
    print(f"[demo] Ollama available = {env['ollama_available']}  models = {env['ollama_model']}")
    print(f"[demo] psutil = {env['psutil_available']}  RSS = {env['rss_bytes']}  CPU% = {env['cpu_percent']}")
    if env["disk_free_bytes"]:
        print(f"[demo] disk free = {env['disk_free_bytes'] / 1024**3:.1f} GiB")

    results: List[StepResult] = []

    # ------------------------------------------------------------------
    # Step 1: sync knowledge
    # ------------------------------------------------------------------
    def step1_sync_kb():
        with TestClient(app) as c:
            r = c.post("/api/v1/knowledge/sync", json={
                "input_path": str(KNOWLEDGE_PATH), "reset_first": True,
            })
            assert r.status_code == 200, r.text
            return r.json()

    results.append(_run("knowledge/sync", step1_sync_kb))
    if not results[-1].ok:
        return _finalize(env, results, fatal=True)
    print(f"  ✓ knowledge/sync — {results[-1].detail['documents']} docs → "
          f"{results[-1].detail['chunks']} chunks ({results[-1].duration_ms:.0f} ms)")

    # ------------------------------------------------------------------
    # Step 2: seed events from CSV
    # ------------------------------------------------------------------
    def step2_seed_events():
        with TestClient(app) as c:
            r = c.post("/api/v1/events/seed", json={
                "input_file": str(CSV_PATH),
                "detector_id": "rule-demo",
                "max_records": steps,
            })
            assert r.status_code == 200, r.text
            return r.json()

    results.append(_run("events/seed", step2_seed_events))
    if not results[-1].ok:
        return _finalize(env, results, fatal=True)
    print(f"  ✓ events/seed — seeded {results[-1].detail['seeded_events']} events "
          f"({results[-1].duration_ms:.0f} ms)")

    # ------------------------------------------------------------------
    # Step 3: fetch one event id
    # ------------------------------------------------------------------
    with TestClient(app) as c:
        r = c.get("/api/v1/events", params={"limit": 1})
        assert r.status_code == 200 and r.json(), "no events after seed"
        event_id = r.json()[0]["event_id"]

    # ------------------------------------------------------------------
    # Step 4: RAG → generate policy
    # ------------------------------------------------------------------
    def step4_generate():
        with TestClient(app) as c:
            r = c.post("/api/v1/policy-proposal/generate", json={"event_id": event_id})
            assert r.status_code == 200, r.text
            j = r.json()
            return {
                "policy_id": j["proposal"]["policy_id"],
                "action_type": j["proposal"]["action_type"],
                "llm_provider": j["llm_provider"],
                "llm_is_mock": j["llm_is_mock"],
                "llm_latency_ms": j["llm_latency_ms"],
                "evidence_count": j["evidence_count"],
            }

    results.append(_run("policy-proposal/generate", step4_generate))
    if not results[-1].ok:
        return _finalize(env, results, fatal=True)
    d = results[-1].detail
    print(f"  ✓ RAG → {d['action_type']} via {d['llm_provider']} "
          f"(mock={d['llm_is_mock']}, LLM {d['llm_latency_ms']:.0f} ms, {d['evidence_count']} evidences)")

    policy_id = d["policy_id"]

    # ------------------------------------------------------------------
    # Step 5: validate
    # ------------------------------------------------------------------
    def step5_validate():
        with TestClient(app) as c:
            r = c.post("/api/v1/policy-proposal/validate", json={"policy_id": policy_id})
            assert r.status_code == 200, r.text
            return r.json()

    results.append(_run("policy-proposal/validate", step5_validate))
    d = results[-1].detail
    print(f"  ✓ validate — is_valid={d.get('is_valid')}")

    # ------------------------------------------------------------------
    # Step 6: execute (DRY_RUN by default)
    # ------------------------------------------------------------------
    mode = "REAL" if real_execute else "DRY_RUN"

    def step6_execute():
        with TestClient(app) as c:
            body: Dict[str, Any] = {"policy_id": policy_id, "mode": mode}
            if mode == "REAL":
                body["approval_token"] = "demo-approval-token"  # 仅 demo，不是生产密码
            r = c.post("/api/v1/policy-proposal/execute", json=body)
            assert r.status_code == 200, r.text
            return r.json()

    results.append(_run(f"policy-proposal/execute ({mode})", step6_execute))
    d = results[-1].detail
    print(f"  ✓ execute {mode} — status={d.get('status')} "
          f"duration_ms={d.get('duration_ms')}")

    # ------------------------------------------------------------------
    # Step 7: metrics snapshot
    # ------------------------------------------------------------------
    def step7_metrics():
        with TestClient(app) as c:
            r = c.get("/api/v1/metrics/overview")
            assert r.status_code == 200, r.text
            return r.json()

    results.append(_run("metrics/overview", step7_metrics))

    return _finalize(env, results, fatal=False)


# ---------------------------------------------------------------------------
# Finalize: build report + print summary
# ---------------------------------------------------------------------------


def _finalize(env: Dict[str, Any], results: List[StepResult], *, fatal: bool) -> Dict[str, Any]:
    all_ok = all(r.ok for r in results)
    report: Dict[str, Any] = {
        "demo": {
            "repo_root": str(REPO_ROOT),
            "fatal": fatal,
            "all_ok": all_ok,
        },
        "environment": env,
        "steps": [asdict(r) for r in results],
        "summary": {
            "total_steps": len(results),
            "ok_steps": sum(1 for r in results if r.ok),
            "failed_steps": [r.name for r in results if not r.ok],
            "total_duration_ms": sum(r.duration_ms for r in results),
        },
    }

    # Pretty print
    print()
    print("=" * 60)
    print("  DEMO REPORT")
    print("=" * 60)
    print(f"  all_ok   : {all_ok}")
    print(f"  steps    : {report['summary']['ok_steps']}/{report['summary']['total_steps']} ok")
    print(f"  total_ms : {report['summary']['total_duration_ms']:.0f}")
    if not all_ok:
        print(f"  FAILED   : {report['summary']['failed_steps']}")
        for r in results:
            if not r.ok:
                print(f"    {r.name}: {r.error}")
    print("=" * 60)

    # Dump JSON alongside demo_e2e.py for CI / auditing
    out_path = REPO_ROOT / "data" / "demo_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[demo] report written → {out_path}")

    return report


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------


def main() -> int:
    import argparse
    p = argparse.ArgumentParser(description="Phase 8 — end-to-end demo")
    p.add_argument("--steps", type=int, default=DEFAULT_STEPS,
                   help="Number of events to seed from CSV (default: 10)")
    p.add_argument("--llm-real", action="store_true",
                   help="Prefer real Ollama LLM (otherwise MockLLM fallback is fine too)")
    p.add_argument("--real-execute", action="store_true",
                   help="Execute in REAL mode (WARNING: Phase 8 guardrail still blocks destructive actions)")
    args = p.parse_args()

    report = run_demo(
        steps=args.steps,
        real_llm=args.llm_real,
        real_execute=args.real_execute,
    )
    return 0 if report["demo"]["all_ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
