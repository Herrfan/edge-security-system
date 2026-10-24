<script setup lang="ts">
import { defineProps } from 'vue'
defineProps<{ size?: number }>()
</script>

<template>
  <div class="spinner" :style="{ width: `${size || 14}px`, height: `${size || 14}px` }" />
</template>

<style scoped>
.spinner {
  display: inline-block;
  border: 2px solid var(--border);
  border-top-color: var(--accent);
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
