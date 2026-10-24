<script setup lang="ts">
/**
 * TrafficAnalysisView — Phase F3 流量文件导入.
 *
 * Upload CSV → POST /api/v1/flows/import (multipart) → IngestionSummary.
 *
 * IMPORTANT: flows/import ONLY parses + ingests into the FlowRecord store.
 * It does NOT run detection or create events. Detection is a separate manual
 * call (POST /detection/predict) requiring a server-side file path — out of
 * scope for the browser.
 *
 * Shows after import:
 *   - source_path (where FastAPI saved the file)
 *   - total_rows / imported / failed
 *   - any errors
 *
 * Then guides user to Events page (which relies on seed-default — see events).
 */
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { importFlows } from '@/api/traffic'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'
import type { IngestionSummary } from '@/types/api'

const router = useRouter()
const fileInput = ref<HTMLInputElement | null>(null)
const selected = ref<File | null>(null)
const busy = ref(false)
const err = ref<string | null>(null)
const summary = ref<IngestionSummary | null>(null)

function onPick(e: Event) {
  const f = (e.target as HTMLInputElement).files?.[0] ?? null
  selected.value = f
  err.value = null
  summary.value = null
}

async function upload() {
  if (!selected.value) { err.value = '请先选择文件'; return }
  busy.value = true; err.value = null; summary.value = null
  try {
    summary.value = await importFlows(selected.value)
  } catch (e: any) {
    err.value = e?.message || '导入失败'
  } finally {
    busy.value = false
  }
}

function gotoEvents() { router.push('/events') }
</script>

<template>
  <div class="traffic">
    <div class="page-head">
      <h2 class="title">流量分析 — 文件导入</h2>
      <DataSourceBadge kind="live" />
    </div>
    <p class="hint">
      上传 CSV / JSONL flow 文件，后端将解析并写入 FlowRecord 存储。
      支持文件扩展名：<code>.csv</code>, <code>.jsonl</code>, <code>.json</code>。
    </p>
    <div class="warn-banner">
      ⚠️ <strong>注意</strong>：此操作 <u>仅导入数据</u>，不自动跑检测生成事件。
      检测和事件生成需在 Events 页面点击 <em>"Seed Events"</em> 按钮（走 rule-demo detector）。
    </div>

    <!-- Picker -->
    <section class="picker-card">
      <input
        ref="fileInput"
        type="file"
        accept=".csv,.jsonl,.json"
        style="display:none"
        @change="onPick"
      />
      <button class="btn-primary" @click="fileInput?.click()" :disabled="busy">
        {{ selected ? '重新选择文件' : '选择文件…' }}
      </button>
      <div v-if="selected" class="file-row">
        <span class="file-name" :title="selected.name">{{ selected.name }}</span>
        <span class="file-size">({{ (selected.size / 1024).toFixed(1) }} KB)</span>
      </div>
      <button
        v-if="selected"
        class="btn-upload"
        :disabled="busy"
        @click="upload"
      >{{ busy ? '导入中…' : '🚀 执行导入' }}</button>
    </section>

    <!-- Error -->
    <section v-if="err" class="err-card">❌ {{ err }}</section>

    <!-- Summary -->
    <section v-if="summary" class="summary-card">
      <div class="sum-head">
        <span class="sum-title">导入完成</span>
        <span class="sum-status" :class="summary.failed === 0 ? 'ok' : 'warn'">
          {{ summary.failed === 0 ? '✅ 全部成功' : `⚠️ ${summary.failed} 行失败` }}
        </span>
      </div>
      <div class="sum-grid">
        <div class="sum-cell">
          <div class="sum-lbl">total_rows</div>
          <div class="sum-val big">{{ summary.total_rows }}</div>
        </div>
        <div class="sum-cell">
          <div class="sum-lbl">imported</div>
          <div class="sum-val big">{{ summary.imported }}</div>
        </div>
        <div class="sum-cell">
          <div class="sum-lbl">failed</div>
          <div class="sum-val big" :class="{ danger: summary.failed > 0 }">{{ summary.failed }}</div>
        </div>
        <div class="sum-cell span-3">
          <div class="sum-lbl">source_path</div>
          <div class="sum-val mono">{{ summary.source_path }}</div>
        </div>
        <div v-if="summary.errors.length" class="sum-cell span-3">
          <div class="sum-lbl">errors ({{ summary.errors.length }})</div>
          <ul class="err-list">
            <li v-for="(e, i) in summary.errors.slice(0, 10)" :key="i">{{ e }}</li>
          </ul>
        </div>
      </div>
      <div class="sum-actions">
        <button class="btn-primary" @click="gotoEvents">🔎 去 Events 页面 Seed 检测 →</button>
      </div>
    </section>

    <!-- What happens panel -->
    <section class="info-card">
      <div class="info-title">流程说明</div>
      <ol class="info-list">
        <li>浏览器通过 <code>multipart/form-data</code> 发送到 <code>POST /api/v1/flows/import</code></li>
        <li>后端写入 <code>data/uploads/{filename}</code> 并通过 CSV/JSONL adapter 解析每行</li>
        <li>校验通过的行写入 FlowRecord 存储（供后续 /detection/predict 读取）</li>
        <li><strong>不跑 detector</strong> — /detection/predict 需要服务端绝对路径，浏览器无法提供</li>
        <li>要生成事件 → 到 Events 页面点 Seed Events（rule-demo detector）</li>
      </ol>
    </section>
  </div>
</template>

<style scoped>
.traffic { display: flex; flex-direction: column; gap: 14px; }
.page-head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.title { margin: 0; font-size: 18px; font-weight: 700; color: var(--text-hi); }
.hint { margin: 0; color: var(--text-sub); font-size: 13px; }
.hint code { background: var(--bg-surface); padding: 1px 5px; border-radius: 3px; color: var(--accent); font-size: 12px; }

.warn-banner { background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.4); border-radius: 6px; padding: 8px 14px; font-size: 12px; color: var(--warn); }
.warn-banner strong { color: #ffc778; }

.picker-card { background: #11132a; border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; display: flex; flex-direction: column; gap: 10px; }
.file-row { display: flex; gap: 10px; align-items: baseline; }
.file-name { font-family: ui-monospace, Consolas, monospace; color: #c3c7dc; max-width: 420px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.file-size { color: var(--text-sub); font-size: 12px; }

.btn-primary { background: var(--accent); color: #fff; border: none; border-radius: 6px; padding: 8px 18px; cursor: pointer; font-weight: 600; font-size: 13px; transition: background .15s; width: fit-content; }
.btn-primary:hover:not(:disabled) { background: #3d7ce6; }
.btn-primary:disabled { background: var(--border); color: #5c6080; cursor: not-allowed; }
.btn-upload { background: var(--ok); color: #0d1117; border: none; border-radius: 6px; padding: 8px 18px; cursor: pointer; font-weight: 700; font-size: 13px; width: fit-content; }
.btn-upload:hover:not(:disabled) { background: #23a978; }
.btn-upload:disabled { background: #1a5d42; color: var(--border); cursor: not-allowed; }

.err-card { background: rgba(240, 68, 82, 0.08); border: 1px solid rgba(240, 68, 82, 0.4); border-radius: 8px; padding: 10px 14px; color: var(--err); font-size: 13px; }

.summary-card { background: #11132a; border: 1px solid var(--border); border-radius: 10px; padding: 16px 18px; }
.sum-head { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 10px; }
.sum-title { font-size: 14px; font-weight: 700; color: var(--ok); }
.sum-status { font-size: 11px; padding: 1px 8px; border-radius: 10px; font-weight: 600; border: 1px solid; }
.sum-status.ok { color: var(--ok); background: rgba(16, 185, 129, 0.15); border-color: rgba(16, 185, 129, 0.4); }
.sum-status.warn { color: var(--warn); background: rgba(245, 158, 11, 0.15); border-color: rgba(245, 158, 11, 0.4); }
.sum-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.sum-cell { background: #1a1d36; border-radius: 6px; padding: 8px 12px; }
.sum-cell.span-3 { grid-column: span 3; }
.sum-lbl { font-size: 10px; text-transform: uppercase; color: var(--text-sub); letter-spacing: 1px; }
.sum-val { font-size: 14px; color: var(--text-hi); font-weight: 600; margin-top: 2px; }
.sum-val.big { font-size: 22px; }
.sum-val.mono { font-family: ui-monospace, Consolas, monospace; font-size: 12px; word-break: break-all; }
.sum-val.danger { color: var(--err); }
.err-list { margin: 4px 0 0; padding-left: 18px; font-family: ui-monospace, Consolas, monospace; font-size: 11px; color: var(--warn); max-height: 180px; overflow: auto; }
.sum-actions { margin-top: 12px; }

.info-card { background: #11132a; border: 1px solid var(--border); border-radius: 10px; padding: 14px 18px; }
.info-title { font-size: 13px; font-weight: 600; color: var(--text-hi); margin-bottom: 8px; }
.info-list { margin: 0; padding-left: 20px; color: #a9aed0; font-size: 12px; line-height: 1.7; }
.info-list code { background: var(--bg-surface); padding: 1px 5px; border-radius: 3px; color: var(--accent); }

/* F6 responsive */
@media (max-width: 768px) {
  .sum-grid { grid-template-columns: repeat(2, 1fr); }
  .sum-cell.span-3 { grid-column: span 2; }
  .file-name { max-width: 260px; }
}
@media (max-width: 480px) {
  .sum-grid { grid-template-columns: 1fr; }
  .sum-cell.span-3 { grid-column: span 1; }
  .btn-upload, .btn-primary { width: 100%; }
}
</style>
