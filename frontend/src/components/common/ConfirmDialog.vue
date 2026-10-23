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
  background: #171a2e; border: 1px solid #2a2e4d; border-radius: 10px;
  padding: 20px 22px; min-width: 320px; max-width: 460px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4);
}
.dialog.danger { border-color: rgba(255, 90, 95, 0.4); }
.title { font-size: 16px; font-weight: 600; margin-bottom: 8px; color: #e4e7f7; }
.body { font-size: 13px; color: #c5c8e4; line-height: 1.6; margin-bottom: 14px; }
.body p { margin: 0 0 6px; }
.actions { display: flex; justify-content: flex-end; gap: 10px; }
.btn { padding: 7px 14px; border-radius: 6px; font-size: 13px; border: 1px solid #2a2e4d; cursor: pointer; }
.btn.cancel { background: #1f2340; color: #e4e7f7; }
.btn.confirm { background: #4f8cff; color: #fff; border-color: #4f8cff; }
.btn.confirm.danger { background: #ff5a5f; border-color: #ff5a5f; }
.btn[disabled] { opacity: 0.5; cursor: not-allowed; }
</style>
