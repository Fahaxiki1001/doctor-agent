import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'Login',
      component: () => import('../views/LoginView.vue'),
    },
    {
      path: '/',
      component: () => import('../components/layout/CLayout.vue'),
      meta: { portal: 'c', requiresAuth: true },
      children: [
        { path: '', redirect: '/chat' },
        { path: 'chat', name: 'Chat', component: () => import('../views/ChatView.vue') },
        { path: 'triage', name: 'Triage', component: () => import('../views/TriageView.vue') },
        {
          path: 'triage/:taskId',
          name: 'TriageDetail',
          component: () => import('../views/TriageView.vue'),
        },
        {
          path: 'knowledge',
          name: 'KnowledgeCenter',
          component: () => import('../views/KnowledgeCenterView.vue'),
        },
        { path: 'reports', name: 'Reports', component: () => import('../views/ReportView.vue') },
        {
          path: 'reports/:reportId',
          name: 'ReportDetail',
          component: () => import('../views/ReportDetailView.vue'),
        },
        {
          path: 'chat/:sessionId',
          name: 'ChatSession',
          component: () => import('../views/ChatView.vue'),
        },
        {
          path: 'personal',
          name: 'Personal',
          component: () => import('../views/PersonalView.vue'),
        },
      ],
    },
    {
      path: '/o',
      component: () => import('../components/layout/OLayout.vue'),
      meta: { portal: 'o', requiresAuth: true, requiresAdmin: true },
      children: [
        { path: '', redirect: '/o/dashboard' },
        {
          path: 'dashboard',
          name: 'Dashboard',
          component: () => import('../views/DashboardView.vue'),
        },
        {
          path: 'knowledge',
          name: 'Knowledge',
          component: () => import('../views/KnowledgeView.vue'),
        },
        { path: 'traces', name: 'Traces', component: () => import('../views/TraceView.vue') },
        {
          path: 'trace/:traceId',
          name: 'TraceDetail',
          component: () => import('../views/TraceView.vue'),
        },
        {
          path: 'evolution',
          name: 'Evolution',
          component: () => import('../views/EvolutionView.vue'),
        },
        { path: 'chat', name: 'OChat', component: () => import('../views/ChatView.vue') },
      ],
    },
  ],
})

function defaultHome(isAdmin: boolean) {
  return isAdmin ? { name: 'Dashboard' } : { name: 'Chat' }
}

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.restore()

  if (!auth.isAuthenticated) {
    if (to.name === 'Login') return true
    return { name: 'Login', query: { redirect: to.fullPath } }
  }

  if (to.name === 'Login') return defaultHome(auth.canAccessOPortal)

  if (to.matched.some((record) => record.meta.requiresAdmin) && !auth.canAccessOPortal) {
    return { name: 'Chat' }
  }

  return true
})

export default router
