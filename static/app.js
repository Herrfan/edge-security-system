/* Edge Security — minimal SPA controller
 * Zero dependencies. Fetches against /api/v1/* (same origin as static).
 * Tabs, approvals, executes, metrics charts.
 */
(function () {
  "use strict";

  const API = "";  // same-origin — static UI is served from the FastAPI app itself
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

  const fmt = {
    date: (iso) => iso ? new Date(iso).toLocaleString() : "—",
    num: (n) => (n == null || isNaN(n)) ? "—" : (typeof n === "number" ? n.toFixed(n % 1 === 0 ? 0 : 3) : n),
  };

  /* ---------- fetch wrapper ---------- */
  async function api(path, opts = {}) {
    const headers = { ...(opts.headers || {}) };
    if (opts.json) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
    }
    const res = await fetch(API + path, { ...opts, headers });
    let body = null;
    const ct = res.headers.get("content-type") || "";
    try { body = ct.includes("application/json") ? await res.json() : await res.text(); }
    catch { body = null; }
    return { ok: res.ok, status: res.status, body };
  }

  function toast(msg, kind = "ok") {
    const t = document.createElement("div");
    t.className = `toast ${kind}`;
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  /* ---------- health ---------- */
  async function checkHealth() {
    const { ok, body } = await api("/health");
    const el = $("#server-status");
    if (ok && body?.status === "ok") {
      el.className = "badge badge-ok";
      el.textContent = "● connected";
      $("#server-info").textContent = `${body.service} v${body.version} · pid ${body.pid}`;
    } else {
      el.className = "badge badge-bad";
      el.textContent = "● offline";
      $("#server-info").textContent = "— check backend";
    }
  }

  /* ---------- tabs ---------- */
  $$(".tab").forEach(t => t.addEventListener("click", () => {
    $$(".tab").forEach(x => x.classList.remove("active"));
    t.classList.add("active");
    $$(".tab-pane").forEach(p => p.classList.remove("active"));
    $(`#tab-${t.dataset.tab}`).classList.add("active");
    // lazy-load active tab
    refreshActiveTab();
  }));

  function refreshActiveTab() {
    const active = $(".tab.active").dataset.tab;
    if (active === "pending") refreshPending();
    else if (active === "events") refreshEvents();
    else if (active === "metrics") refreshMetrics();
    else if (active === "all") refreshAll();
  }

  /* ---------- card template ---------- */
  function actionOf(p) {
    const a = p.action_type || p.actionType || "UNKNOWN";
    return a;
  }

  function severityOf(p) {
    return (p.risk_level || p.severity || "MEDIUM").toUpperCase();
  }

  function paramsHtml(p) {
    const params = p.parameters || {};
    const ip = params.ip || "";
    const port = params.port || "";
    const pps = params.max_pps || "";
    if (p.action_type === "BLOCK_IP")     return `ip: ${ip}`;
    if (p.action_type === "BLOCK_PORT")   return `port: ${port}`;
    if (p.action_type === "RATE_LIMIT")   return `ip: ${ip} · max_pps: ${pps}`;
    if (p.action_type === "ALERT_ONLY")   return `severity: ${severityOf(p)}`;
    if (p.action_type === "NO_ACTION")    return "—";
    return JSON.stringify(params).slice(0, 120);
  }

  function buildCard(p, opts = {}) {
    const tpl = $("#card-template").content.firstElementChild.cloneNode(true);
    const h = tpl.querySelector(".card-head");
    const body = tpl.querySelector(".card-body");
    const actions = tpl.querySelector(".card-actions");

    h.querySelector(".action-badge").textContent = actionOf(p);
    const sev = h.querySelector(".severity-tag");
    sev.textContent = severityOf(p);
    sev.classList.add(severityOf(p));
    const st = h.querySelector(".status-tag");
    st.textContent = p.status || "—";
    st.classList.add(p.status || "");

    body.querySelector(".rationale").textContent = p.rationale || "—";
    body.querySelector(".params").textContent = paramsHtml(p);

    if (p.policy_id) {
      const idDiv = document.createElement("div");
      idDiv.style.cssText = "font-size:11px;color:#5a5f8a;font-family:ui-monospace;";
      idDiv.textContent = `policy_id=${p.policy_id}`;
      body.appendChild(idDiv);
    }

    const pid = p.policy_id;
    const status = p.status;

    if (opts.showApprove && status === "NEEDS_APPROVAL") {
      const ap = document.createElement("button");
      ap.className = "btn btn-ok"; ap.textContent = "✓ Approve";
      ap.addEventListener("click", () => approve(pid, true));
      const rj = document.createElement("button");
      rj.className = "btn btn-danger"; rj.textContent = "✗ Reject";
      rj.addEventListener("click", () => approve(pid, false));
      actions.appendChild(ap); actions.appendChild(rj);
    }
    if (opts.showExecute && (status === "APPROVED" || status === "NEEDS_APPROVAL")) {
      const ex = document.createElement("button");
      ex.className = "btn btn-primary"; ex.textContent = "▶ DRY_RUN execute";
      ex.addEventListener("click", () => execute(pid, "DRY_RUN"));
      actions.appendChild(ex);
    }
    if (status === "EXECUTED") {
      const done = document.createElement("span");
      done.style.cssText = "font-size:11px;color:#29c38b;padding:4px 0;";
      done.textContent = "● already executed";
      actions.appendChild(done);
    }
    if (status === "REJECTED") {
      const done = document.createElement("span");
      done.style.cssText = "font-size:11px;color:#ff5a5f;padding:4px 0;";
      done.textContent = "● rejected";
      actions.appendChild(done);
    }
    if (status === "NEEDS_APPROVAL") {
      const note = document.createElement("span");
      note.style.cssText = "font-size:11px;color:#ffb454;padding:4px 0;";
      note.textContent = "● 待人工审批";
      actions.appendChild(note);
    }

    return tpl;
  }

  /* ---------- pending ---------- */
  async function refreshPending() {
    const { ok, body } = await api("/api/v1/policy-proposals?status=NEEDS_APPROVAL&limit=100");
    const root = $("#pending-cards"); root.innerHTML = "";
    $("#pending-empty").classList.add("hidden");
    if (!ok || !body?.length) {
      $("#pending-empty").classList.remove("hidden");
      return;
    }
    body.forEach(p => root.appendChild(buildCard(p, { showApprove: true, showExecute: true })));
  }

  $("#btn-refresh").addEventListener("click", refreshPending);

  /* ---------- approve / reject ---------- */
  async function approve(policy_id, approve) {
    const reason = prompt(approve ? "Approve reason (optional)" : "Reject reason (optional)", "") || null;
    const { ok, status, body } = await api("/api/v1/policy-proposal/approve", {
      method: "POST",
      json: { policy_id, approve, reason, approver: "ui" },
    });
    if (ok) toast(`${approve ? "Approved" : "Rejected"} → ${body.status}`, "ok");
    else toast(`Approve failed (${status}): ${body?.detail || body}`, "err");
    refreshActiveTab();
  }

  /* ---------- execute ---------- */
  async function execute(policy_id, mode) {
    const { ok, status, body } = await api("/api/v1/policy-proposal/execute", {
      method: "POST",
      json: { policy_id, mode },
    });
    if (ok && body.status === "SUCCEEDED") toast(`Execute ${body.status}`, "ok");
    else toast(`Execute ${body.status || "failed"} (${status})`, ok ? "ok" : "err");
    refreshActiveTab();
  }

  /* ---------- all proposals ---------- */
  async function refreshAll() {
    const status = $("#all-status").value;
    const url = status ? `/api/v1/policy-proposals?status=${status}&limit=100`
                       : "/api/v1/policy-proposals?limit=100";
    const { ok, body } = await api(url);
    const root = $("#all-cards"); root.innerHTML = "";
    if (!ok || !body?.length) {
      root.innerHTML = `<div class="empty">没有策略 ${status ? `（status=${status}）` : ""}</div>`;
      return;
    }
    body.forEach(p => root.appendChild(buildCard(p, { showApprove: true, showExecute: true })));
  }
  $("#btn-all-refresh").addEventListener("click", refreshAll);
  $("#all-status").addEventListener("change", refreshAll);

  /* ---------- events ---------- */
  async function refreshEvents() {
    const sev = $("#events-severity").value;
    const url = sev ? `/api/v1/events?severity=${encodeURIComponent(sev)}&limit=50`
                    : "/api/v1/events?limit=50";
    const { ok, body } = await api(url);
    const tbl = $("#events-table");
    if (!ok) { tbl.innerHTML = `<div class="empty">Load failed</div>`; return; }
    if (!body?.length) { tbl.innerHTML = `<div class="empty">no events — seed first</div>`; return; }
    tbl.innerHTML = `
      <tr><th>event_id</th><th>severity</th><th>label</th><th>score</th><th>asset</th><th>status</th><th>trace</th></tr>
      ${body.map(e => `
        <tr>
          <td style="font-family:ui-monospace;font-size:11px">${e.event_id}</td>
          <td class="severity-td"><span class="${e.severity}">${e.severity}</span></td>
          <td>${e.predicted_label || "—"}</td>
          <td>${fmt.num(e.score)}</td>
          <td>${e.asset_id || "—"}</td>
          <td>${e.status || "—"}</td>
          <td style="font-family:ui-monospace;font-size:11px;color:#5a5f8a">${e.trace_id || "—"}</td>
        </tr>`).join("")}
    `;
  }
  $("#btn-events-refresh").addEventListener("click", refreshEvents);
  $("#events-severity").addEventListener("change", refreshEvents);
  $("#btn-seed").addEventListener("click", async () => {
    const sample = "data/samples/flows_sample.csv";
    const { ok, body } = await api(`/api/v1/flows/seed-policy?path=${encodeURIComponent(sample)}`, { method: "POST" });
    if (ok) toast(`Seeded ${body.imported_flows} flows`, "ok");
    else toast(`Seed failed: ${body?.detail || body}`, "err");
    refreshEvents();
  });

  /* ---------- metrics ---------- */
  async function refreshMetrics() {
    const { ok, body } = await api("/api/v1/metrics/overview");
    const grid = $("#metrics-grid"); grid.innerHTML = "";
    const raw = $("#metrics-raw"); raw.classList.add("hidden");
    if (!ok) { grid.innerHTML = `<div class="empty">Load failed</div>`; return; }
    const metrics = body.metrics || {};
    const entries = Object.entries(metrics);
    if (!entries.length) { grid.innerHTML = `<div class="empty">No metrics yet — run demo_e2e.py or seed events</div>`; return; }

    entries.forEach(([name, block]) => {
      const card = document.createElement("div");
      card.className = "metric-card";
      card.innerHTML = `<div class="metric-name">${name}</div>`;
      const series = block.series || [];
      if (!series.length) {
        card.classList.add("unavailable");
        card.innerHTML += `<div class="metric-value">unavailable</div>`;
      } else {
        series.slice(0, 3).forEach(s => {
          const labels = Object.entries(s).filter(([k]) => k !== "value").map(([k, v]) => `${k}=${v}`).join(" · ");
          card.innerHTML += `<div class="metric-value">${fmt.num(s.value)}</div>
                             <div class="metric-labels">${labels || "—"}</div>`;
        });
        if (series.length > 3) {
          const more = document.createElement("div");
          more.style.cssText = "font-size:11px;color:#5a5f8a;margin-top:4px;";
          more.textContent = `+${series.length - 3} more series`;
          card.appendChild(more);
        }
      }
      grid.appendChild(card);
    });
    // dump raw overview
    raw.textContent = JSON.stringify(body, null, 2);
  }
  $("#btn-metrics-refresh").addEventListener("click", refreshMetrics);

  /* ---------- init ---------- */
  async function init() {
    await checkHealth();
    refreshPending();
    // poll health every 20s
    setInterval(checkHealth, 20000);
  }
  init();
})();
