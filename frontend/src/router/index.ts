import { createRouter, createWebHistory } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('@/views/LoginView.vue'),
      meta: { public: true, title: '登录' },
    },
    {
      path: '/',
      component: () => import('@/layouts/AppLayout.vue'),
      children: [
        { path: '', name: 'dashboard', component: () => import('@/views/DashboardView.vue'), meta: { title: '总览看板' } },
        { path: 'cases', name: 'cases', component: () => import('@/views/CasesView.vue'), meta: { title: '用例库' } },
        { path: 'plans', name: 'plans', component: () => import('@/views/PlansView.vue'), meta: { title: '测试计划' } },
        {
          path: 'plans/:id',
          name: 'plan-detail',
          component: () => import('@/views/PlanDetailView.vue'),
          meta: { title: '执行清单' },
        },
        { path: 'compare', name: 'compare', component: () => import('@/views/CompareView.vue'), meta: { title: '版本回归对比' } },
        { path: 'stability', name: 'stability', component: () => import('@/views/StabilityView.vue'), meta: { title: '稳定性压测' } },
        { path: 'ai', name: 'ai', component: () => import('@/views/AiDraftsView.vue'), meta: { title: 'AI 用例草稿' } },
        {
          path: 'automation',
          name: 'automation',
          component: () => import('@/views/AutomationView.vue'),
          meta: { title: '自动化回传' },
        },
        {
          path: 'users',
          name: 'users',
          component: () => import('@/views/UsersView.vue'),
          meta: { title: '用户与权限', adminOnly: true },
        },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  if (to.meta.public) return true
  if (!auth.isLoggedIn) return { path: '/login', query: { redirect: to.fullPath } }

  if (!auth.user) {
    try {
      await auth.fetchMe()
    } catch {
      auth.logout()
      return { path: '/login' }
    }
  }
  if (to.meta.adminOnly && !auth.isAdmin) return { path: '/' }
  return true
})

router.afterEach((to) => {
  document.title = to.meta.title ? `${to.meta.title} · 车机测试数据平台` : '车机测试数据平台'
})

export default router
