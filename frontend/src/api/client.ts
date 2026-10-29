import axios, { AxiosError } from 'axios'
import { ElMessage } from 'element-plus'

export const TOKEN_KEY = 'ivi_token'

export const http = axios.create({ baseURL: '/api/v1', timeout: 30000 })

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let redirecting = false

http.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ detail?: unknown }>) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail
    // FastAPI 校验错误是数组，取第一条 msg 展示，避免弹一坨 JSON
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail) && detail.length
          ? String((detail[0] as { msg?: string }).msg ?? '参数校验失败')
          : '请求失败，请稍后重试'

    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      if (!redirecting && location.pathname !== '/login') {
        redirecting = true
        ElMessage.warning('登录状态已失效，请重新登录')
        location.href = '/login'
      }
    } else {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  },
)
