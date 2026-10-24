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
.layout { min-height: 100vh; display: flex; flex-direction: column; }
.body { display: flex; flex: 1; }
.content { flex: 1; padding: 24px; overflow: auto; }
.fade-enter-active, .fade-leave-active { transition: opacity 0.15s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

/* F6 responsive — sidebar collapses on narrow viewports */
@media (max-width: 768px) {
  .content { padding: 16px; }
}
</style>
