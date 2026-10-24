<script setup lang="ts">
/**
 * StatusTag — SOC v2 版.
 * 用纯 CSS 变量色板 (style.css :root tokens), 支持 severity / status / action 三种语义.
 */
defineProps<{
  severity?: string
  status?: string
  action?: string
  size?: 'sm' | 'md'
}>()
</script>

<template>
  <span
    class="status-tag"
    :class="[
      { 'size-sm': size === 'sm' },
      severity && `sev-${severity.toLowerCase()}`,
      status && `sts-${status.toLowerCase()}`,
      action && `act-${action.toLowerCase()}`,
    ]"
  >
    <slot />
  </span>
</template>

<style scoped>
.status-tag {
  display: inline-block;
  font-size: 11px; padding: 2px 8px;
  border-radius: var(--radius-sm);
  font-weight: 600;
  letter-spacing: 0.3px;
  line-height: 1.4;
}
.size-sm { font-size: 10px; padding: 1px 6px; }

/* === Severity colors === */
.sev-critical, .sev-critical-high    { background: var(--err-soft);   color: var(--err);   border: 1px solid rgba(240, 68, 82, 0.3); }
.sev-high                             { background: var(--warn-soft);  color: var(--warn);  border: 1px solid rgba(245, 158, 11, 0.3); }
.sev-medium                           { background: var(--info-soft);  color: var(--info-blue); border: 1px solid rgba(59, 130, 246, 0.3); }
.sev-low                              { background: var(--ok-soft);    color: var(--ok);    border: 1px solid rgba(16, 185, 129, 0.3); }
.sev-info                             { background: rgba(100, 116, 139, 0.18); color: var(--text-dim); border: 1px solid rgba(100, 116, 139, 0.3); }

/* === Policy status colors === */
.sts-needs-approval                   { background: var(--warn-soft);  color: var(--warn);  border: 1px solid rgba(245, 158, 11, 0.3); }
.sts-needs-validation                 { background: rgba(100, 116, 139, 0.18); color: var(--text-dim); border: 1px solid rgba(100, 116, 139, 0.3); }
.sts-approved                         { background: var(--ok-soft);    color: var(--ok);    border: 1px solid rgba(16, 185, 129, 0.3); }
.sts-rejected                         { background: var(--err-soft);   color: var(--err);   border: 1px solid rgba(240, 68, 82, 0.3); }
.sts-executed                         { background: var(--accent);     color: #fff; }
.sts-expired, .sts-draft              { background: rgba(100, 116, 139, 0.18); color: var(--text-dim); border: 1px solid rgba(100, 116, 139, 0.3); }

/* === Action type colors === */
.act-block-ip, .act-block-port, .act-rate-limit { background: var(--info-soft); color: var(--info-blue); border: 1px solid rgba(59, 130, 246, 0.3); }
.act-alert-only                                  { background: var(--warn-soft); color: var(--warn); border: 1px solid rgba(245, 158, 11, 0.3); }
.act-no-action                                   { background: rgba(100, 116, 139, 0.18); color: var(--text-dim); border: 1px solid rgba(100, 116, 139, 0.3); }
</style>
