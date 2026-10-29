import { defineStore } from 'pinia'
import { computed, ref } from 'vue'

import { authApi } from '@/api'
import { TOKEN_KEY } from '@/api/client'
import type { Role, UserInfo } from '@/api/types'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem(TOKEN_KEY) ?? '')
  const user = ref<UserInfo | null>(null)
  const loading = ref(false)

  const isLoggedIn = computed(() => Boolean(token.value))
  const role = computed<Role | ''>(() => user.value?.role ?? '')
  // 与后端一致的能力划分：admin/lead 可写，executor 可提交执行结果，viewer 只读
  const canWrite = computed(() => role.value === 'admin' || role.value === 'lead')
  const canExecute = computed(() => canWrite.value || role.value === 'executor')
  const isAdmin = computed(() => role.value === 'admin')

  async function login(email: string, password: string) {
    loading.value = true
    try {
      const data = await authApi.login(email, password)
      token.value = data.access_token
      user.value = data.user
      localStorage.setItem(TOKEN_KEY, data.access_token)
    } finally {
      loading.value = false
    }
  }

  async function fetchMe() {
    if (!token.value) return
    user.value = await authApi.me()
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
  }

  return { token, user, loading, isLoggedIn, role, canWrite, canExecute, isAdmin, login, fetchMe, logout }
})
