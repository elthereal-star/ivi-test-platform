<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import Icon from '@/components/Icon.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const navs = [
  { group: '测试执行', items: [
    { name: 'dashboard', path: '/', label: '总览看板', icon: 'dashboard' },
    { name: 'cases', path: '/cases', label: '用例库', icon: 'cases' },
    { name: 'plans', path: '/plans', label: '测试计划', icon: 'plans' },
  ] },
  { group: '数据洞察', items: [
    { name: 'compare', path: '/compare', label: '版本回归对比', icon: 'compare' },
    { name: 'stability', path: '/stability', label: '稳定性压测', icon: 'stability' },
  ] },
  { group: '效率工具', items: [
    { name: 'ai', path: '/ai', label: 'AI 用例草稿', icon: 'ai' },
    { name: 'automation', path: '/automation', label: '自动化回传', icon: 'automation' },
  ] },
]

const roleLabel = computed(() => {
  const map: Record<string, string> = { admin: '管理员', lead: '测试负责人', executor: '执行测试员', viewer: '只读访客' }
  return map[auth.role] ?? auth.role
})

const isActive = (path: string) => (path === '/' ? route.path === '/' : route.path.startsWith(path))

function logout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="shell">
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-mark">IV</div>
        <div class="brand-text">
          <strong>车机测试数据平台</strong>
          <span>IVI TEST PLATFORM</span>
        </div>
      </div>

      <template v-for="group in navs" :key="group.group">
        <div class="nav-group">{{ group.group }}</div>
        <div
          v-for="item in group.items"
          :key="item.name"
          class="nav-item"
          :class="{ active: isActive(item.path) }"
          @click="router.push(item.path)"
        >
          <Icon :name="item.icon" />
          <span>{{ item.label }}</span>
        </div>
      </template>

      <template v-if="auth.isAdmin">
        <div class="nav-group">系统</div>
        <div class="nav-item" :class="{ active: isActive('/users') }" @click="router.push('/users')">
          <Icon name="users" />
          <span>用户与权限</span>
        </div>
      </template>

      <div class="sidebar-foot">
        小牛 D21x · 演示数据<br />
        v0.1.0
      </div>
    </aside>

    <div class="main">
      <header class="topbar">
        <h1>{{ route.meta.title }}</h1>
        <div class="spacer" />
        <div class="who">
          <div class="avatar">{{ (auth.user?.full_name ?? '?').slice(0, 1) }}</div>
          <div>
            <div>{{ auth.user?.full_name }}</div>
            <div class="muted" style="font-size: 11.5px">{{ roleLabel }}</div>
          </div>
          <el-button text size="small" @click="logout">
            <Icon name="logout" :size="15" />
            <span style="margin-left: 4px">退出</span>
          </el-button>
        </div>
      </header>

      <main class="content">
        <router-view />
      </main>
    </div>
  </div>
</template>
