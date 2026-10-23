<script setup lang="ts">
/**
 * Knowledge Base — Phase F2.
 * Full closed loop on retrieval side:
 *   sync default (or custom path) → index status → search → hits.
 */
import { onMounted, ref } from 'vue'
import {
  syncDefaultKnowledge,
  retrievalStatus,
  searchRetrieval,
} from '@/api/retrieval'
import type { RetrievalResult, KnowledgeSyncResult } from '@/api/retrieval'
import LoadingSpinner from '@/components/common/LoadingSpinner.vue'
import ErrorBanner from '@/components/common/ErrorBanner.vue'
import DataSourceBadge from '@/components/common/DataSourceBadge.vue'
import RetrievalSearchForm from '@/components/retrieval/RetrievalSearchForm.vue'
import RetrievalHitList from '@/components/retrieval/RetrievalHitList.vue'

const syncing = ref(false)
const syncResult = ref<KnowledgeSyncResult | null>(null)
const syncErr = ref('')

const status = ref<Record<string, unknown> | null>(null)
const statusLoading = ref(true)
const statusErr = ref('')

const searching = ref(false)
const searchResult = ref<RetrievalResult | null>(null)
const searchErr = ref('')

async function loadStatus() {
  statusLoading.value = true
  statusErr.value = ''
  try {
    status.value = await retrievalStatus()
  } catch (e) {
    statusErr.value = (e as Error).message
  } finally {
    statusLoading.value = false
  }
}

async function doSync() {
  syncing.value = true
  syncResult.value = null
  syncErr.value = ''
  try {
    syncResult.value = await syncDefaultKnowledge()
    await loadStatus()
  } catch (e) {
    syncErr.value = (e as Error).message
  } finally {
    syncing.value = false
  }
}

async function onSearch(payload: { query: string; mode: 'hybrid' | 'keyword' | 'vector' | null; topK: number }) {
  searching.value = true
  searchResult.value = null
  searchErr.value = ''
  try {
    searchResult.value = await searchRetrieval(payload.query, payload.mode, payload.topK)
  } catch (e) {
    searchErr.value = (e as Error).message
  } finally {
    searching.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div>
        <h2>威胁知识库</h2>
        <div class="page-sub">
          <DataSourceBadge kind="live" />
          <span>数据源：<code>POST /api/v1/knowledge/sync</code> · <code>POST /api/v1/retrieval</code> · <code>GET /retrieval/status</code></span>
        </div>
        <div class="page-note">
          内置安全知识 <code>data/knowledge/security_knowledge.jsonl</code> · 同步后可检索威胁情报、CVE、Mitigation Playbooks。
        </div>
      </div>
    </div>

    <!-- Status + Sync row -->
    <div class="status-row">
      <div class="panel">
        <div class="panel-title">知识库状态</div>
        <div v-if="statusLoading" class="center-sm"><LoadingSpinner :size="14" /> 加载中…</div>
        <div v-else-if="statusErr" class="err">{{ statusErr }}</div>
        <div v-else class="kv">
          <div>
            <span>索引条目</span>
            <code>{{ (status?.count as number) ?? 0 }}</code>
          </div>
        </div>
      </div>

      <div class="panel sync-panel">
        <div class="panel-title">Sync</div>
        <button class="btn btn-sync" :disabled="syncing" @click="doSync">
          <LoadingSpinner v-if="syncing" :size="12" />
          <span v-else>📥</span> {{ syncing ? '同步中…' : 'Sync Default Knowledge (reset)' }}
        </button>
        <div v-if="syncResult" class="sync-result">
          ✓ {{ syncResult.documents }} docs · {{ syncResult.chunks }} chunks · via {{ syncResult.provider }}
        </div>
        <div v-if="syncErr" class="err">{{ syncErr }}</div>
      </div>
    </div>

    <ErrorBanner v-if="searchErr" :message="searchErr" />

    <!-- Search form + results -->
    <div class="search-block">
      <div class="panel">
        <div class="panel-title">检索 Threat Intelligence</div>
        <RetrievalSearchForm @search="onSearch" />
      </div>

      <div v-if="searching" class="center-sm"><LoadingSpinner :size="20" /> 检索中…</div>

      <div v-else-if="searchResult" class="panel results-panel">
        <RetrievalHitList
          :hits="searchResult.hits"
          :mode="searchResult.mode"
          :provider="searchResult.provider"
          :is-mock="searchResult.is_mock"
          :status="searchResult.status"
        />
      </div>
    </div>
  </div>
</template>

<style scoped>
.page { padding: 0; }
.page-head { margin-bottom: 16px; }
.page h2 { font-size: 18px; font-weight: 600; margin: 0 0 4px; }
.page-sub { font-size: 12px; color: #8a8fb8; margin-bottom: 6px; }
.page-sub code { font-family: ui-monospace, Menlo, monospace; }
.page-note { font-size: 12px; color: #ffb454; background: rgba(255, 180, 84, 0.08); padding: 6px 10px; border-radius: 6px; display: inline-block; }
.page-note code { font-family: ui-monospace, Menlo, monospace; }

.status-row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 14px; }
.panel { background: #171a2e; border: 1px solid #2a2e4d; border-radius: 8px; padding: 14px 16px; }
.panel-title { font-size: 11px; color: #8a8fb8; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 10px; }
.kv { display: flex; flex-direction: column; gap: 6px; font-size: 13px; }
.kv > div { display: flex; justify-content: space-between; align-items: center; }
.kv span { color: #8a8fb8; }
.kv code { font-family: ui-monospace, Menlo, monospace; background: #141729; padding: 2px 8px; border-radius: 4px; color: #4f8cff; font-size: 13px; }

.sync-panel { display: flex; flex-direction: column; gap: 10px; }
.btn-sync {
  background: #29c38b; color: #0f1120; border: none; padding: 8px 16px; border-radius: 6px;
  font-size: 13px; font-weight: 600; cursor: pointer; display: inline-flex; gap: 6px; align-items: center;
}
.btn-sync:disabled { opacity: 0.6; cursor: not-allowed; }
.sync-result { color: #29c38b; font-size: 12px; }
.err { color: #ff5a5f; font-size: 12px; padding: 6px 0; }

.search-block { display: flex; flex-direction: column; gap: 12px; }
.results-panel { min-height: 120px; }
.center-sm { display: flex; gap: 8px; align-items: center; justify-content: center; padding: 16px; color: #8a8fb8; font-size: 12px; }
</style>
