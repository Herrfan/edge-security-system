<script setup lang="ts">
import TopBar from './TopBar.vue'
import Sidebar from './Sidebar.vue'
</script>

<template>
  <div class="layout">
    <a href="#main-content" class="skip-link">跳过导航</a>
    <TopBar />
    <div class="body">
      <Sidebar />
      <main id="main-content" class="content" tabindex="-1">
        <router-view v-slot="{ Component }">
          <transition name="fade" mode="out-in">
            <component :is="Component" />
          </transition>
        </router-view>
      </main>
    </div>
  </div>
</template>

<style scoped>
.layout { min-height: 100vh; display: flex; flex-direction: column; background: var(--bg-root); }
.body { display: flex; flex: 1; min-height: calc(100vh - var(--topbar-h)); }
.content { flex: 1; padding: var(--space-6); overflow: auto; background: var(--bg-root); }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

@media (max-width: 768px) {
  .content { padding: var(--space-4); }
}
</style>
