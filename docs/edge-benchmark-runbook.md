# Edge Device Benchmark — Runbook

Phase 13 harness: `scripts/edge_benchmark.py`. Cross-platform but designed for
Linux edge devices (Raspberry Pi 4B/5, Jetson Nano, N100 mini PC, etc.).

## One-shot run (Linux edge device)

```bash
# 1. Clone + install on target device
git clone https://github.com/Herrfan/edge-security-system.git
cd edge-security-system
pip install -e . psutil

# 2. Pull Ollama models (if not already)
ollama pull qwen2.5:3b
ollama pull nomic-embed-text

# 3. Run the harness
python scripts/edge_benchmark.py
# → data/edge_benchmark_report.json
```

## What the harness measures

| Section | Method | Linux exclusive? |
|---|---|---|
| Host CPU cores + model + freq | psutil + /proc/cpuinfo + /sys/class/thermal | Yes (thermal) |
| RAM / Swap | /proc/meminfo + psutil | — |
| Network interfaces + I/O | psutil.net_if_addrs + net_io_counters | — |
| Disk total / free + 4KiB fsync latency | shutil.disk_usage + tempfile | — |
| Accelerators (GPU/NPU) | import torch / tensorrt / openvino + `/dev/apex_*` glob | Partial (Coral glob) |
| Ollama reachable? models? size? | HTTP `/api/tags` | — |
| **Import memory profile** | Spawns fresh subprocess per module, measures RSS delta | — |
| **E2E wall clock** | subprocess `demo_e2e --steps 6` | — |
| **Concurrent smoke** | ThreadPoolExecutor × TestClient workers × rounds | — |
| **pytest -q wall clock** | subprocess pytest | — |

## Per-phase breakdown (in report.demo_e2e.demo_steps)

| Step | Approx duration on N100 CPU | Bottleneck |
|---|---|---|
| knowledge/sync | ~9s | sqlite-vec 768-dim upsert, 30 docs |
| events/seed | ~160 ms | CSV ingest + detection |
| **policy-proposal/generate** | **~26.5 s** | qwen2.5:3b CPU inference (dominant) |
| policy-proposal/validate | ~95 ms | deterministic rules (CIDR / port / TTL) |
| policy-proposal/execute (DRY_RUN) | ~130 ms | sync adapter dispatch |
| metrics/overview | ~37 ms | Registry.to_overview() serialization |

**Key insight**: >70% of demo wall clock is the LLM call. On GPU / Coral NPU / VPU
this should collapse to < 2 s. That's why the harness reports
`"gpu_inference_latency_ms": "待验证"` — this machine is CPU-only.

## Import profile (highest RSS delta first) — your machine will differ

```
app.main                    +63 MB   ← FastAPI + lifespan + all routes
app.core.database           +43 MB   ← SQLAlchemy engine + 6 ORMs
app.services.rag_service    +32 MB   ← pulls llm + retrieval
app.adapters.llm.base       +25 MB   ← httpx + requests
app.services.retrieval      +14 MB   ← sqlite-vec embedding dim mismatch → 2x memory
app.core.config             +16 MB   ← Pydantic Settings + lru_cache
app.adapters.backends       +15 MB   ← shlex + subprocess import chain
```

Heaviest import on ANY edge device will still be `app.main` because it pulls
all routes + lifespan. On a Raspberry Pi 4 (4 GB RAM) this is tight — consider
a "headless" FastAPI app that omits `/detection` and `/policy-proposal/*` if
those aren't needed on that edge node.

## Concurrent smoke — what it tells you

`workers=4, rounds=3` → 36 total tasks. Aggregated to `p50 / p95 / max` latency
per endpoint.

- On N100 CPU TestClient: health p50 = 4 ms, seed p50 = 0.3 ms (all 24 ok here —
  your runbook author made sure `/health` is registered at root, not
  `/api/v1/health`).
- On uvicorn workers with real HTTP: expect 2–10× these numbers due to socket
  + event loop overhead — the current harness uses TestClient so it measures
  **in-process** dispatch latency, not real HTTP. The report section
  `not_measured.gunicorn_100_workers_rps` calls this out explicitly.

## What NOT to do

- **Do NOT set `allow_real_execution=True`** on an edge device with real
  firewall state until you have verified `run_atomic` rollback actually works —
  Phase 12 tested it here on Windows with EchoBackend, but we have zero
  evidence it applies correctly to a production nftables tree on a remote host.
  The harness's `not_measured.real_iptables_apply_latency` field exists so
  you will **not** fabricate a number by flipping the flag on a lark.

- **Do NOT omit the report's `not_measured` keys from your deliverable.** The
  harness writes them for a reason — they're the TODOs for Phase 14+. If you
  paste the benchmark report into a presentation, keep them there. A report
  that says "we measured X, we did NOT measure Y" is honest and useful. A
  report that only has measured numbers is a sell.

## Report schema (high-level)

```jsonc
{
  "meta": { "generated_at_utc": "...", "runner_host": "...", "repo_head": "..." },
  "host":  { "cpu": {...}, "memory": {...}, "thermal": {...}, "network": {...},
             "disk": {...}, "accelerators": {...} },
  "ollama": { "ollama_reachable": true, "models": [{"name":"...", "size_bytes":...}] },
  "import_profile": [{"module": "...", "delta": 65280, ...}],   // delta in bytes
  "demo_e2e":        { "wall_clock_ms": 37225, "demo_steps": [...] },
  "concurrent_smoke": { "workers": 4, "by_task": { "health": {"p50_ms":4.0,...} } },
  "pytest_full_wall_clock_ms": 177690,
  "not_measured": {
     "real_iptables_apply_latency": "...待验证...",
     "gpu_inference_latency_ms":   "...待验证...",
     "gunicorn_100_workers_rps":   "...待验证...",
     // ...
  }
}
```

## Interpreting results — reference baseline (Phase 13 self-benchmark)

Device: **Intel N100 (4 cores, 4 GB?) — actually this dev box is 16 cores / 32 GB**,
so your edge device numbers will be worse. For a **real edge device**:

| Metric | N100 self-benchmark (CPU only) | Expected on Pi 4B (4 GB) | Notes |
|---|---|---|---|
| pytest -q total wall | 177,690 ms | ~250,000 ms | Slower Python + slower disk |
| demo wall clock | 37,225 ms | ~45,000 ms | 70% LLM time, CPU-bound |
| app.main import RSS | +63 MB | +63 MB (same) | Same code, same import chain |
| GPU inference | **待验证** | N/A (no GPU) | Use Coral / OpenVINO VPU |
| nftables apply | **待验证** | N/A (Windows harness) | Linux-only |
| Real firewall concurrency | **待验证** | N/A | Needs gunicorn + nginx |

Any number you pull out of this harness goes in alongside the "待验证"
sentences — never replace them.
