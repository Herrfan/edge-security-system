<script setup lang="ts">
import { computed, ref } from 'vue'

const props = withDefaults(
  defineProps<{
    title?: string
    body?: string
    confirmLabel?: string
    cancelLabel?: string
    danger?: boolean
  }>(),
  { title: '确认操作', confirmLabel: '确认', cancelLabel: '取消', danger: false },
)
const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const confirming = ref(false)
const bodyLines = computed(() => (props.body ?? '').split('\n').filter(Boolean))
</script>

<template>
  <div class="mask" @click.self="emit('cancel')">
    <div class="dialog" :class="{ danger }">
      <div class="title">{{ title }}</div>
      <div v-if="bodyLines.length" class="body">
        <p v-for="(l, i) in bodyLines" :key="i">{{ l }}</p>
      </div>
      <div class="actions">
        <button class="btn cancel" :disabled="confirming" @click="emit('cancel')">{{ cancelLabel }}</button>
        <button
          class="btn confirm"
          :class="{ danger }"
          :disabled="confirming"
          @click="emit('confirm'); confirming = true"
        >
          {{ confirming ? '处理中…' : confirmLabel }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.mask {
  position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5);
  display: flex; align-items: center; justify-content: center;
  z-index: 1000;
}
.dialog {
  background: var(--bg-panel); border: 1px solid var(--border); border-radius: 10px;
  padding: 20px 22px; min-width: 320px; max-width: 460px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
}
.dialog.danger { border-color: rgba(240, 68, 82, 0.4); }
.title { font-size: 16px; font-weight: 600; margin-bottom: 8px; color: var(--text-hi); }
.body { font-size: 13px; color: var(--text-mid); line-height: 1.6; margin-bottom: 14px; }
.body p { margin: 0 0 6px; }
.actions { display: flex; justify-content: flex-end; gap: 10px; }
.btn { padding: 7px 14px; border-radius: 6px; font-size: 13px; border: 1px solid var(--border); cursor: pointer; }
.btn.cancel { background: var(--bg-surface); color: var(--text-hi); }
.btn.confirm { background: var(--accent); color: #fff; border-color: var(--accent); }
.btn.confirm.danger { background: var(--err); border-color: var(--err); }
.btn[disabled] { opacity: 0.5; cursor: not-allowed; }
</style>
