<script setup lang="ts">
defineProps<{ size?: number }>()
</script>

<template>
  <span class="spinner" :style="{ width: size ?? 16, height: size ?? 16 }" />
</template>

<style scoped>
.spinner {
  display: inline-block;
  border: 2px solid #2a2e4d;
  border-top-color: #4f8cff;
  border-radius: 50%;
  animation: spin 0.7s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
</style>
