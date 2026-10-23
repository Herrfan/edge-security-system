<script setup lang="ts">
defineProps<{
  severity?: string
  status?: string
  action?: string
}>()
</script>

<template>
  <span
    class="status-tag"
    :class="{
      [`sev-${severity?.toLowerCase()}`]: severity,
      [`sts-${status?.toLowerCase()}`]: status,
      [`act-${action?.toLowerCase()}`]: action,
    }"
  >
    <slot />
  </span>
</template>

<style scoped>
.status-tag {
  font-size: 11px;
  padding: 2px 7px;
  border-radius: 4px;
  font-weight: 600;
  letter-spacing: 0.3px;
}

.sev-critical { background: rgba(255, 90, 95, 0.18); color: #ff5a5f; }
.sev-high     { background: rgba(255, 180, 84, 0.2);  color: #ffb454; }
.sev-medium   { background: rgba(79, 140, 255, 0.15); color: #4f8cff; }
.sev-low      { background: rgba(41, 195, 139, 0.15); color: #29c38b; }
.sev-info     { background: rgba(138, 143, 184, 0.2); color: #8a8fb8; }

.sts-needs-approval { background: rgba(255, 180, 84, 0.18); color: #ffb454; }
.sts-approved       { background: rgba(41, 195, 139, 0.15); color: #29c38b; }
.sts-rejected       { background: rgba(255, 90, 95, 0.18);  color: #ff5a5f; }
.sts-executed       { background: rgba(79, 140, 255, 0.15); color: #4f8cff; }
.sts-needs-validation,
.sts-expired,
.sts-draft          { background: rgba(138, 143, 184, 0.2); color: #8a8fb8; }

.act-block-ip,
.act-block-port,
.act-rate-limit     { background: rgba(79, 140, 255, 0.15); color: #4f8cff; }
.act-alert-only     { background: rgba(255, 180, 84, 0.2); color: #ffb454; }
.act-no-action      { background: rgba(138, 143, 184, 0.2); color: #8a8fb8; }
</style>
