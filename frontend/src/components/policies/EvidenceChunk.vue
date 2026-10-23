<script setup lang="ts">
/**
 * Displays a single retrieval evidence chunk as a small card.
 * Used inside PolicyDetailView when showing evidences retrieved for a proposal.
 */
defineProps<{
  chunk_id: string
  document_id: string
  source?: string
  title?: string
  content?: string
  retrieval_score?: number
  retrieval_method?: string
}>()
</script>

<template>
  <div class="evidence">
    <div class="evidence-head">
      <span class="mono">{{ chunk_id }}</span>
      <span class="doc-id">doc: {{ document_id }}</span>
      <span v-if="retrieval_score !== undefined" class="score">{{ (retrieval_score * 100).toFixed(1) }}%</span>
    </div>
    <div v-if="title" class="evidence-title">{{ title }}</div>
    <div v-if="content" class="evidence-content">{{ content }}</div>
    <div class="evidence-meta">
      <span v-if="source">📄 {{ source }}</span>
      <span v-if="retrieval_method">🔍 {{ retrieval_method }}</span>
    </div>
  </div>
</template>

<style scoped>
.evidence {
  background: #141729;
  border: 1px solid #2a2e4d;
  border-radius: 6px;
  padding: 10px 12px;
  font-size: 12px;
}
.evidence-head { display: flex; gap: 10px; align-items: center; margin-bottom: 6px; }
.mono { font-family: ui-monospace, Menlo, monospace; color: #8a8fb8; font-size: 11px; }
.doc-id { font-family: ui-monospace, Menlo, monospace; color: #5a5f8a; font-size: 11px; }
.score { margin-left: auto; background: rgba(79, 140, 255, 0.15); color: #4f8cff; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: 600; }
.evidence-title { color: #c5c8e4; font-weight: 600; margin-bottom: 4px; font-size: 13px; }
.evidence-content { color: #8a8fb8; line-height: 1.6; max-height: 80px; overflow: hidden; font-size: 12px; white-space: pre-wrap; }
.evidence-meta { display: flex; gap: 10px; margin-top: 6px; color: #5a5f8a; font-size: 11px; }
</style>
