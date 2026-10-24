<script setup lang="ts">
/**
 * AuditView — Phase F5 审计日志占位.
 *
 * KEY DIFFERENCE FROM EvaluationView: 审计基础设施 70% 已存在 — ExecutionRecord
 * 和 SecurityEvent 都带 trace_id 字段，execute / approve / generate 的响应
 * 也返回 execution_id + trace_id。缺口是：
 *   - 后端没有 GET /audit-logs 查询端点
 *   - 没有按 trace_id / 时间范围 / actor 过滤
 *   - 没有审计事件的持久化 store（ExecutionRecord 存 SQLAlchemy 但没 list API）
 *
 * 本页面列出：后端已有字段（可追溯）+ 缺失端点（需实现）。
 */
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>审计日志</h2>
        <div class="page-sub">
          <DataSourceBadge kind="blocked" />
          <span>数据源：<span class="muted">未接入</span> — 后端无 GET /audit-logs 查询端点</span>
        </div>
      </div>
    </div>

    <!-- Distinction banner — 基础设施已存在 70% -->
    <section class="distinction-banner">
      <div class="db-icon">ℹ️</div>
      <div class="db-body">
        <div class="db-title">与评估中心不同 — 审计基础设施 70% 已存在</div>
        <div class="db-desc">
          <span class="highlight-green">好消息：</span>
          后端 <code>ExecutionRecord</code> 和 <code>SecurityEvent</code>
          模型已经持久化了 <code>trace_id</code>、<code>execution_id</code>、
          <code>rollback_status</code>、<code>duration_ms</code> 等字段。
          每次 <code>POST /policy-proposal/execute</code> 都返回完整记录。
          缺口仅是 <span class="highlight-orange">GET /audit-logs 查询端点</span>。
        </div>
      </div>
    </section>

    <!-- What we ALREADY have (backend) -->
    <section class="infra-card">
      <div class="infra-title">✅ 后端已有的可追溯字段</div>
      <table class="infra-table">
        <thead>
          <tr><th>模型</th><th>字段</th><th>来源端点</th></tr>
        </thead>
        <tbody>
          <tr><td rowspan="4" class="model-cell">ExecutionRecord</td><td><code>execution_id</code></td><td><code>POST /policy-proposal/execute</code> (200)</td></tr>
          <tr><td><code>policy_id</code> + <code>mode</code> + <code>status</code></td><td>同上</td></tr>
          <tr><td><code>trace_id</code></td><td>同上</td></tr>
          <tr><td><code>stdout_summary</code> + <code>stderr_summary</code> + <code>rollback_status</code></td><td>同上</td></tr>
          <tr><td rowspan="2" class="model-cell">SecurityEvent</td><td><code>trace_id</code></td><td><code>GET /events</code> 列表</td></tr>
          <tr><td><code>model_id</code> + <code>model_version</code></td><td>同上</td></tr>
          <tr><td>PolicyProposal</td><td><code>policy_id</code> + <code>approver</code> + <code>reason</code></td><td><code>POST /policy-proposal/approve</code></td></tr>
        </tbody>
      </table>
      <div class="code-ref">
        持久化：<code>app/stores/execution_store.py</code> + <code>app/repositories/event_repository.py</code>
      </div>
    </section>

    <!-- What's MISSING -->
    <section class="gap-card">
      <div class="gap-title">🚧 缺失的查询端点</div>
      <ul class="gap-list">
        <li><code>GET /api/v1/audit-logs?trace_id=xxx</code> — 按 trace_id 查完整执行链</li>
        <li><code>GET /api/v1/audit-logs?time_from=&amp;time_to=</code> — 按时间范围过滤</li>
        <li><code>GET /api/v1/audit-logs?actor=agent@edge</code> — 按 approver 过滤</li>
        <li><code>GET /api/v1/executions?policy_id=</code> — 某策略的所有 dry-run / real 执行历史</li>
        <li><code>GET /api/v1/audit-logs?action=approve</code> — 审批动作列表</li>
      </ul>
      <div class="gap-hint">
        <strong>实现成本估算：</strong>~200 行 Python（复用现有 SQLAlchemy store + 新增 1 个 routes/audit.py + 1 个 Pydantic 模型）。
      </div>
    </section>

    <!-- When done, this page will show -->
    <section class="planned-card">
      <div class="planned-title">🔮 当 GET /audit-logs 就绪时，本页将展示</div>
      <div class="planned-grid">
        <div class="planned-cell">
          <div class="pc-icon">🔗</div>
          <div class="pc-title">Trace 时间线</div>
          <div class="pc-desc">按 trace_id 聚合 generate → validate → execute → approve 全链路，每个步骤标注操作者 + 时间 + 结果</div>
        </div>
        <div class="planned-cell">
          <div class="pc-icon">📜</div>
          <div class="pc-title">审计列表</div>
          <div class="pc-desc">时间倒序 + severity 过滤 + actor 过滤。支持点击展开查看 stdout/stderr summary</div>
        </div>
        <div class="planned-cell">
          <div class="pc-icon">🏓</div>
          <div class="pc-title">回滚历史</div>
          <div class="pc-desc">rollback_status != SUCCEEDED 的执行高亮红色 — 一眼看到哪次 apply 失败</div>
        </div>
      </div>
    </section>
  </div>
</template>

<style scoped>
.page { padding: 0; }
.page h2 { font-size: 18px; font-weight: 600; margin: 0 0 4px; color: #e4e7f7; }
.page-sub { font-size: 12px; color: #8a8fb8; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.page-sub .muted { color: #ffb454; }

.distinction-banner { background: rgba(79, 140, 255, 0.07); border: 1px solid rgba(79, 140, 255, 0.3); border-radius: 10px; padding: 14px 18px; display: flex; gap: 14px; align-items: flex-start; margin-bottom: 14px; }
.db-icon { font-size: 22px; }
.db-title { font-size: 13px; font-weight: 700; color: #4f8cff; margin-bottom: 6px; }
.db-desc { font-size: 12px; color: #c3c7dc; line-height: 1.7; }
.db-desc code { background: #1f2340; padding: 1px 5px; border-radius: 3px; color: #4f8cff; font-family: ui-monospace, Consolas, monospace; }
.highlight-green { color: #29c38b; font-weight: 600; }
.highlight-orange { color: #ffb454; font-weight: 600; }

.infra-card { background: #11132a; border: 1px solid rgba(41, 195, 139, 0.3); border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; }
.infra-title { font-size: 13px; font-weight: 700; color: #29c38b; margin-bottom: 12px; }
.infra-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.infra-table th { text-align: left; padding: 6px 10px; border-bottom: 1px solid #2a2e4d; color: #8a8fb8; font-weight: 500; font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; }
.infra-table td { padding: 6px 10px; border-bottom: 1px solid #1a1d36; color: #c3c7dc; vertical-align: top; }
.infra-table code { font-family: ui-monospace, Consolas, monospace; background: #1f2340; padding: 1px 5px; border-radius: 3px; color: #c5c8e4; font-size: 11px; }
.model-cell { color: #8a8fb8; font-weight: 600; }
.code-ref { margin-top: 10px; font-size: 11px; color: #8a8fb8; }
.code-ref code { font-family: ui-monospace, Consolas, monospace; background: #1f2340; padding: 1px 5px; border-radius: 3px; }

.gap-card { background: #11132a; border: 1px solid rgba(255, 90, 95, 0.3); border-radius: 10px; padding: 14px 18px; margin-bottom: 14px; }
.gap-title { font-size: 13px; font-weight: 700; color: #ff5a5f; margin-bottom: 10px; }
.gap-list { margin: 0; padding-left: 22px; font-size: 12px; color: #c3c7dc; line-height: 1.9; }
.gap-list code { font-family: ui-monospace, Consolas, monospace; background: #1f2340; padding: 1px 5px; border-radius: 3px; color: #ff5a5f; }
.gap-hint { margin-top: 10px; font-size: 11px; color: #8a8fb8; background: rgba(255, 90, 95, 0.08); padding: 6px 10px; border-radius: 6px; }

.planned-card { background: #11132a; border: 1px solid #2a2e4d; border-radius: 10px; padding: 14px 18px; }
.planned-title { font-size: 13px; font-weight: 700; color: #e4e7f7; margin-bottom: 12px; }
.planned-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.planned-cell { background: #1a1d36; border-radius: 8px; padding: 12px 14px; border: 1px solid #232642; }
.pc-icon { font-size: 20px; margin-bottom: 4px; }
.pc-title { font-size: 12px; font-weight: 700; color: #e4e7f7; margin-bottom: 4px; }
.pc-desc { font-size: 11px; color: #8a8fb8; line-height: 1.6; }

/* F6 responsive */
@media (max-width: 768px) {
  .planned-grid { grid-template-columns: repeat(2, 1fr); }
  .infra-table { font-size: 11px; }
}
@media (max-width: 480px) {
  .planned-grid { grid-template-columns: 1fr; }
  .infra-table td, .infra-table th { padding: 5px 6px; }
  .model-cell { display: none; }
}
</style>
