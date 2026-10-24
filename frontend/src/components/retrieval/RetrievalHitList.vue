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
.tag { font-size: 11px; padding: 2px 8px; border-radius: 10px; background: var(--bg-panel); color: var(--text-sub); font-family: var(--font-mono); }
.tag.hit-count { background: rgba(52, 120, 246, 0.15); color: var(--accent); }
.tag.mock { background: rgba(245, 158, 11, 0.15); color: var(--warn); }
.tag.degraded { background: rgba(240, 68, 82, 0.15); color: var(--err); }

.hit-list { display: flex; flex-direction: column; gap: 6px; }
.hit {
  display: flex; gap: 12px; align-items: center;
  background: var(--bg-nav); border: 1px solid var(--border); border-radius: 6px; padding: 10px 12px;
}
.hit-rank {
  width: 28px; height: 28px; border-radius: 50%;
  background: rgba(52, 120, 246, 0.15); color: var(--accent);
  display: inline-flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 700; font-family: var(--font-mono);
  flex-shrink: 0;
}
.hit-body { flex: 1; min-width: 0; }
.hit-head { display: flex; gap: 10px; align-items: center; margin-bottom: 4px; }
.mono { font-family: var(--font-mono); color: var(--text-mid); font-size: 12px; }
.doc { color: var(--text-sub); font-size: 12px; }
.hit-meta { display: flex; gap: 14px; align-items: center; font-size: 11px; color: var(--text-dim); }
.score-bar { display: inline-flex; align-items: center; gap: 6px; }
.score-fill { display: inline-block; width: 80px; height: 4px; background: var(--border); border-radius: 2px; position: relative; overflow: hidden; }
.score-fill::after { content: ''; position: absolute; inset: 0; background: var(--ok); width: 100%; border-radius: 2px; }
.score-num { color: var(--ok); font-weight: 600; font-family: var(--font-mono); }
.dist { font-family: var(--font-mono); }
.empty { text-align: center; color: var(--text-sub); padding: 30px 20px; border: 1px dashed var(--border); border-radius: 8px; }
.empty strong { color: var(--warn); }
</style>
