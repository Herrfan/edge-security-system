<script setup lang="ts">
/**
 * EvaluationView — Phase F4 评估中心占位.
 *
 * Dedicated placeholder explaining WHAT evaluation WOULD show and WHY it's
 * blocked right now. More informative than the generic PlaceholderView:
 * shows the planned metrics (Precision / Recall / F1), detector comparison,
 * experiment list, and the backend code paths that need to be built first.
 *
 * Backend reality: no /evaluation or /experiment endpoints exist. The only
 * detector-related APIs are:
 *   POST /detection/train       — fits sklearn baseline on a labelled file
 *   POST /detection/predict     — runs a named detector over a server-side file
 *   GET  /metrics/overview      — exposes edgy_detections_total / edgy_* latency
 *                                counters (event counts, not per-detector stats)
 *
 * The gap is: there is NO labelled test set store, NO per-experiment run history,
 * NO confusion matrix computation, and NO Precision/Recall/F1 aggregation.
 * Until those backend primitives exist, this page stays informational.
 */
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>评估中心</h2>
        <div class="page-sub">
          <DataSourceBadge kind="blocked" />
          <span>数据源：<span class="muted">未接入</span> — 后端暂无实验管理 API</span>
        </div>
      </div>
    </div>

    <!-- Blocked banner -->
    <section class="blocked-banner">
      <div class="bb-icon">🚧</div>
      <div class="bb-body">
        <div class="bb-title">本页面尚未接入后端 API</div>
        <div class="bb-desc">
          评估指标（Precision / Recall / F1 / Confusion Matrix）需要后端
          提供实验管理、标注数据集、检测结果追溯三条基础设施。
          当前后端只有 <code>/detection/predict</code>（单次推理）和
          <code>/detection/train</code>（单次拟合），无法生成评估报表。
        </div>
      </div>
    </section>

    <!-- What this page WILL show (when backend ready) -->
    <section class="planned-card">
      <div class="planned-title">当后端就绪时，这里将展示</div>

      <div class="planned-grid">
        <div class="planned-cell">
          <div class="pc-icon">🎯</div>
          <div class="pc-title">Precision / Recall / F1</div>
          <div class="pc-desc">按 detector 聚合。rule-demo vs sklearn-baseline 对比表</div>
        </div>
        <div class="planned-cell">
          <div class="pc-icon">📊</div>
          <div class="pc-title">Confusion Matrix</div>
          <div class="pc-desc">BENIGN / ANOMALY / ATTACK 三分类矩阵 + per-class ROC</div>
        </div>
        <div class="planned-cell">
          <div class="pc-icon">🧪</div>
          <div class="pc-title">实验列表</div>
          <div class="pc-desc">每次 train/predict 记录 run_id + 数据集版本 + 模型版本 + 指标快照</div>
        </div>
        <div class="planned-cell">
          <div class="pc-icon">⏱️</div>
          <div class="pc-title">延迟分布</div>
          <div class="pc-desc">edgy_detection_latency_ms 直方图 + p50/p95/p99</div>
        </div>
        <div class="planned-cell">
          <div class="pc-icon">📐</div>
          <div class="pc-title">准确率 vs 假阳性权衡</div>
          <div class="pc-desc">阈值扫描曲线（detector score cutoff 调优）</div>
        </div>
        <div class="planned-cell">
          <div class="pc-icon">🏷️</div>
          <div class="pc-title">标注数据集管理</div>
          <div class="pc-desc">上传 labelled CSV → 自动切 train/test → 锁定版本</div>
        </div>
      </div>
    </section>

    <!-- Backend gap analysis -->
    <section class="gap-card">
      <div class="gap-title">🔎 后端缺口分析</div>
      <table class="gap-table">
        <thead>
          <tr><th>需要的后端能力</th><th>当前状态</th><th>关联代码</th></tr>
        </thead>
        <tbody>
          <tr>
            <td>标注数据集持久化 + 版本管理</td>
            <td><span class="status-no">缺失</span></td>
            <td class="mono">app/services/ingestion.py (只有 FlowRecord，无 labelled split)</td>
          </tr>
          <tr>
            <td>实验运行记录（run_id, model_version, dataset_version）</td>
            <td><span class="status-no">缺失</span></td>
            <td class="mono">app/services/detection.py 只有 _detectors dict（内存注册）</td>
          </tr>
          <tr>
            <td>Confusion Matrix + Precision/Recall/F1 计算</td>
            <td><span class="status-no">缺失</span></td>
            <td class="mono">无</td>
          </tr>
          <tr>
            <td>GET /api/v1/evaluations (实验列表)</td>
            <td><span class="status-no">缺失</span></td>
            <td class="mono">app/api/routes/ — 无 evaluation.py</td>
          </tr>
          <tr>
            <td>GET /metrics/overview 已有 counter 计数</td>
            <td><span class="status-ok">已有 (但不够)</span></td>
            <td class="mono">edgy_detections_total, edgy_detection_latency_ms</td>
          </tr>
          <tr>
            <td>POST /detection/train + /predict</td>
            <td><span class="status-ok">已有 (单次)</span></td>
            <td class="mono">app/api/routes/detection.py</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.page { padding: 0; }
.page h2 { font-size: 18px; font-weight: 600; margin: 0 0 4px; color: #e4e7f7; }
.page-sub { font-size: 12px; color: #8a8fb8; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
.page-sub .muted { color: #ffb454; }
.page-sub code { font-family: ui-monospace, Consolas, monospace; }

.blocked-banner { background: rgba(255, 90, 95, 0.08); border: 1px solid rgba(255, 90, 95, 0.35); border-radius: 10px; padding: 16px 20px; display: flex; gap: 16px; align-items: flex-start; margin-bottom: 16px; }
.bb-icon { font-size: 28px; }
.bb-title { font-size: 14px; font-weight: 700; color: #ff5a5f; margin-bottom: 6px; }
.bb-desc { font-size: 12px; color: #c3c7dc; line-height: 1.7; }
.bb-desc code { background: #1f2340; padding: 1px 5px; border-radius: 3px; color: #4f8cff; font-family: ui-monospace, Consolas, monospace; }

.planned-card { background: #11132a; border: 1px solid #2a2e4d; border-radius: 10px; padding: 16px 20px; margin-bottom: 16px; }
.planned-title { font-size: 13px; font-weight: 700; color: #e4e7f7; margin-bottom: 14px; }
.planned-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.planned-cell { background: #1a1d36; border-radius: 8px; padding: 12px 14px; border: 1px solid #232642; }
.pc-icon { font-size: 20px; margin-bottom: 4px; }
.pc-title { font-size: 12px; font-weight: 700; color: #e4e7f7; margin-bottom: 4px; }
.pc-desc { font-size: 11px; color: #8a8fb8; line-height: 1.6; }

.gap-card { background: #11132a; border: 1px solid #2a2e4d; border-radius: 10px; padding: 16px 20px; }
.gap-title { font-size: 13px; font-weight: 700; color: #e4e7f7; margin-bottom: 12px; }
.gap-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.gap-table th { text-align: left; padding: 7px 10px; border-bottom: 1px solid #2a2e4d; color: #8a8fb8; font-weight: 500; font-size: 10px; text-transform: uppercase; letter-spacing: 0.8px; }
.gap-table td { padding: 7px 10px; border-bottom: 1px solid #1a1d36; color: #c3c7dc; }
.gap-table tr:last-child td { border-bottom: none; }
.status-no { color: #ff5a5f; font-weight: 600; background: rgba(255, 90, 95, 0.12); padding: 1px 8px; border-radius: 10px; font-size: 11px; }
.status-ok { color: #29c38b; font-weight: 600; background: rgba(41, 195, 139, 0.12); padding: 1px 8px; border-radius: 10px; font-size: 11px; }
.mono { font-family: ui-monospace, Consolas, monospace; color: #8a8fb8; font-size: 11px; }

/* F6 responsive */
@media (max-width: 768px) {
  .planned-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .planned-grid { grid-template-columns: 1fr; }
  .gap-table { font-size: 11px; }
  .gap-table td, .gap-table th { padding: 6px; }
}
</style>
