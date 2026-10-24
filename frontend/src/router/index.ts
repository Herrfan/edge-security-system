import { createRouter, createWebHashHistory } from 'vue-router'
import DefaultLayout from '@/layouts/DefaultLayout.vue'
import DashboardView from '@/views/DashboardView.vue'
import EventsListView from '@/views/EventsListView.vue'
import KnowledgeBaseView from '@/views/KnowledgeBaseView.vue'
import PolicyWorkbenchView from '@/views/PolicyWorkbenchView.vue'
import SettingsView from '@/views/SettingsView.vue'
import TrafficAnalysisView from '@/views/TrafficAnalysisView.vue'
import EvaluationView from '@/views/EvaluationView.vue'
import AuditView from '@/views/AuditView.vue'
import NotFoundView from '@/views/NotFoundView.vue'

// Hash history so the SPA works whether served at / (prod FastAPI mount)
// or /ui (dev vite dev) — no base path to configure.
export default createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      component: DefaultLayout,
      children: [
        { path: '', redirect: '/dashboard' },
        { path: 'dashboard',  name: 'dashboard',  component: DashboardView },
        { path: 'traffic',    name: 'traffic',    component: TrafficAnalysisView },
        { path: 'events',     name: 'events',     component: EventsListView },
        { path: 'knowledge',  name: 'knowledge',  component: KnowledgeBaseView },
        { path: 'policies',   name: 'policies',   component: PolicyWorkbenchView },
        { path: 'evaluation', name: 'evaluation', component: EvaluationView },
        { path: 'audit',      name: 'audit',      component: AuditView },
        { path: 'settings',   name: 'settings',   component: SettingsView },
      ],
    },
    { path: '/:pathMatch(.*)*', component: NotFoundView },
  ],
})
