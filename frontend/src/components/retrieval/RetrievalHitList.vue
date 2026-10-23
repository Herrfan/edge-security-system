<script setup lang="ts">
/**
 * Displays retrieval hits from /api/v1/retrieval.
 * Each hit shows chunk_id + document_id + score + distance.
 */
defineProps<{
  hits: { chunk_id: string; document_id: string; rowid: number; distance: number; score: number }[]
  mode?: string
  provider?: string
  isMock?: boolean
  status?: 'OK' | 'DEGRADED' | 'EMPTY' | 'ERROR'
}>()
</script>

<template>
  <div class="wrap">
    <div v-if="status && status !== 'EMPTY'" class="meta">
      <span class="tag hit-count">{{ hits.length }} hits</span>
      <span v-if="mode" class="tag">mode: {{ mode }}</span>
      <span v-if="provider" class="tag">provider: {{ provider }}</span>
      <span v-if="isMock" class="tag mock">mock LLM</span>
      <span v-if="status === 'DEGRADED'" class="tag degraded">DEGRADED</span>
    </div>

    <div v-if="hits.length" class="hit-list">
      <div v-for="(h, i) in hits" :key="h.rowid" class="hit">
        <div class="hit-rank">#{{ i + 1 }}</div>
        <div class="hit-body">
          <div class="hit-head">
            <span class="mono">{{ h.chunk_id }}</span>
            <span class="doc">doc: <span class="mono">{{ h.document_id }}</span></span>
          </div>
          <div class="hit-meta">
            <span class="score-bar">
              <span class="score-fill" :style="{ width: `${(h.score * 100).toFixed(1)}%` }" />
              <span class="score-num">{{ (h.score * 100).toFixed(1) }}%</span>
            </span>
            <span class="dist">distance: {{ h.distance.toFixed(3) }}</span>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="status === 'EMPTY'" class="empty">
      知识库为空 · 先在"威胁知识库"点击 <strong>sync default</strong> 索引内置安全知识
    </div>
    <div v-else-if="!hits.length" class="empty">No hits.</div>
  </div>
</template>

<style scoped>
.wrap { display: flex; flex-direction: column; gap: 10px; }
.meta { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.tag { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: #171a2e; color: #8a8fb8; font-family: ui-monospace, Menlo, monospace; }
.tag.hit-count { background: rgba(79, 140, 255, 0.15); color: #4f8cff; }
.tag.mock { background: rgba(255, 180, 84, 0.15); color: #ffb454; }
.tag.degraded { background: rgba(255, 90, 95, 0.15); color: #ff5a5f; }

.hit-list { display: flex; flex-direction: column; gap: 6px; }
.hit {
  display: flex; gap: 12px; align-items: center;
  background: #141729; border: 1px solid #2a2e4d; border-radius: 6px; padding: 10px 12px;
}
.hit-rank {
  width: 28px; height: 28px; border-radius: 50%;
  background: rgba(79, 140, 255, 0.15); color: #4f8cff;
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; font-family: ui-monospace, Menlo, monospace;
  flex-shrink: 0;
}
.hit-body { flex: 1; min-width: 0; }
.hit-head { display: flex; gap: 10px; align-items: center; margin-bottom: 4px; }
.mono { font-family: ui-monospace, Menlo, monospace; color: #c5c8e4; font-size: 12px; }
.doc { color: #8a8fb8; font-size: 12px; }
.hit-meta { display: flex; gap: 14px; align-items: center; font-size: 11px; color: #5a5f8a; }
.score-bar { display: inline-flex; align-items: center; gap: 6px; }
.score-fill { display: inline-block; width: 80px; height: 4px; background: #2a2e4d; border-radius: 2px; position: relative; overflow: hidden; }
.score-fill::after { content: ''; position: absolute; inset: 0; background: #29c38b; width: 100%; border-radius: 2px; }
.score-num { color: #29c38b; font-weight: 600; font-family: ui-monospace, Menlo, monospace; }
.dist { font-family: ui-monospace, Menlo, monospace; }
.empty { text-align: center; color: #8a8fb8; padding: 30px 20px; border: 1px dashed #2a2e4d; border-radius: 8px; }
.empty strong { color: #ffb454; }
</style>
