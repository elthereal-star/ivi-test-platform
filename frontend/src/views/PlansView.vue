<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'

import { planApi } from '@/api'
import type { PlanInfo } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const plans = ref<PlanInfo[]>([])
const loading = ref(false)
const dialog = ref(false)
const scope = ref<'all' | 'empty'>('all')

const form = reactive({
  code: '',
  name: '',
  fw_version: '',
  device_model: 'D21x',
  device_sn: 'SN2026000123',
  remark: '',
})

async function load() {
  loading.value = true
  try {
    plans.value = (await planApi.list({ size: 50 })).items
  } finally {
    loading.value = false
  }
}

onMounted(load)

function openCreate() {
  const now = new Date()
  const week = Math.ceil((now.getDate() + 3) / 7)
  Object.assign(form, {
    code: `R${now.getFullYear()}.${String(now.getMonth() + 1).padStart(2, '0')}-W${week}`,
    name: '',
    fw_version: '',
    device_model: 'D21x',
    device_sn: 'SN2026000123',
    remark: '',
  })
  scope.value = 'all'
  dialog.value = true
}

async function create() {
  if (!form.code || !form.name || !form.fw_version) {
    ElMessage.warning('编号、名称、固件版本为必填')
    return
  }
  const plan = await planApi.create({ ...form, case_ids: [] }, scope.value === 'all')
  ElMessage.success(`已创建，纳入 ${plan.stats.total} 条用例`)
  dialog.value = false
  await load()
  router.push(`/plans/${plan.id}`)
}

const statusLabel: Record<string, string> = { draft: '草稿', running: '进行中', completed: '已完成', archived: '已归档' }
</script>

<template>
  <div>
    <div class="toolbar">
      <span class="muted" style="font-size: 12.5px">一个计划 = 一次回归批次，绑定固件版本与设备，是版本对比的基准单位</span>
      <div class="spacer" />
      <el-button size="small" @click="load">刷新</el-button>
      <el-button v-if="auth.canWrite" type="primary" size="small" @click="openCreate">新建批次</el-button>
    </div>

    <div v-loading="loading" class="grid" style="grid-template-columns: repeat(auto-fill, minmax(420px, 1fr))">
      <div v-for="p in plans" :key="p.id" class="card" style="cursor: pointer" @click="router.push(`/plans/${p.id}`)">
        <div class="card-head" style="margin-bottom: 10px">
          <h3 class="mono" style="font-size: 13.5px">{{ p.code }}</h3>
          <span class="pill" :class="p.status === 'running' ? 'pill-p2' : p.status === 'completed' ? 'pill-pass' : 'pill-skip'">
            {{ statusLabel[p.status] ?? p.status }}
          </span>
          <div class="spacer" />
          <span class="muted" style="font-size: 12px">固件 {{ p.fw_version }}</span>
        </div>

        <div style="font-size: 14px; margin-bottom: 12px">{{ p.name }}</div>

        <div style="display: flex; gap: 20px; font-size: 12.5px; margin-bottom: 12px">
          <span class="muted">执行率 <b class="num" style="color: var(--text)">{{ p.stats.exec_rate }}%</b></span>
          <span class="muted">通过率 <b class="num" :class="p.stats.pass_rate >= 85 ? 'ok' : 'warn'">{{ p.stats.pass_rate }}%</b></span>
          <span class="muted">失败 <b class="num bad">{{ p.stats.failed }}</b></span>
          <span v-if="p.stats.p0_failed" class="bad">P0 阻塞 {{ p.stats.p0_failed }}</span>
        </div>

        <div class="progress-line">
          <i :style="{ width: `${p.stats.exec_rate}%`, background: p.stats.p0_failed ? 'var(--bad)' : 'var(--primary)' }" />
        </div>
        <div class="muted" style="font-size: 11.5px; margin-top: 8px">
          {{ p.device_model }} · {{ p.device_sn || '未绑定设备' }} · 共 {{ p.stats.total }} 条用例
        </div>
      </div>
    </div>

    <el-dialog v-model="dialog" title="新建回归批次" width="560px">
      <el-form label-width="92px">
        <el-form-item label="批次编号" required>
          <el-input v-model="form.code" placeholder="R2026.11-W1" />
        </el-form-item>
        <el-form-item label="批次名称" required>
          <el-input v-model="form.name" placeholder="1.3.1.0 回归（第 1 周）" />
        </el-form-item>
        <el-form-item label="固件版本" required>
          <el-input v-model="form.fw_version" placeholder="1.3.1.0" />
        </el-form-item>
        <el-form-item label="设备型号">
          <el-input v-model="form.device_model" />
        </el-form-item>
        <el-form-item label="设备 SN">
          <el-input v-model="form.device_sn" />
        </el-form-item>
        <el-form-item label="用例范围">
          <el-radio-group v-model="scope">
            <el-radio value="all">纳入全部生效用例</el-radio>
            <el-radio value="empty">先建空批次，稍后挑选</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.remark" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
