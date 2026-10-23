<script setup lang="ts">
/**
 * Search form for /api/v1/retrieval.
 * Emits { query, mode, topK } on submit.
 */
import { ref } from 'vue'

const emit = defineEmits<{
  (e: 'search', payload: { query: string; mode: 'hybrid' | 'keyword' | 'vector' | null; topK: number }): void
}>()

const query = ref('')
const mode = ref<'hybrid' | 'keyword' | 'vector' | ''>('hybrid')
const topK = ref(10)

function submit() {
  if (!query.value.trim()) return
  emit('search', {
    query: query.value.trim(),
    mode: mode.value || null,
    topK: topK.value,
  })
}

defineExpose({ submit })
</script>

<template>
  <form class="form" @submit.prevent="submit">
    <div class="row">
      <input
        v-model="query"
        class="q-input"
        placeholder="搜索威胁知识库 (e.g. ICMP flood mitigation)"
        @keydown.enter.prevent="submit"
      />
      <button type="submit" class="btn">🔍 检索</button>
    </div>
    <div class="opts">
      <select v-model="mode" class="opt-input">
        <option value="hybrid">hybrid (default)</option>
        <option value="keyword">keyword (BM25)</option>
        <option value="vector">vector (embedding)</option>
      </select>
      <select v-model="topK" class="opt-input">
        <option :value="5">top 5</option>
        <option :value="10">top 10</option>
        <option :value="20">top 20</option>
        <option :value="50">top 50</option>
      </select>
    </div>
  </form>
</template>

<style scoped>
.form { display: flex; flex-direction: column; gap: 8px; }
.row { display: flex; gap: 8px; }
.q-input {
  flex: 1; background: #171a2e; border: 1px solid #2a2e4d; color: #e4e7f7;
  padding: 10px 14px; border-radius: 6px; font-size: 14px;
}
.q-input:focus { border-color: #4f8cff; outline: none; }
.btn {
  background: #4f8cff; color: #fff; border: none; padding: 0 20px; border-radius: 6px;
  font-size: 13px; font-weight: 600; cursor: pointer;
}
.opts { display: flex; gap: 10px; align-items: center; }
.opt-input {
  background: #171a2e; border: 1px solid #2a2e4d; color: #c5c8e4;
  padding: 6px 10px; border-radius: 5px; font-size: 12px; font-family: inherit;
}
</style>
