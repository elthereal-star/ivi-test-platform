<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { planApi } from '@/api'
import type { ExecRow, PlanInfo } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const planId = route.params.id as string

const plan = ref<PlanInfo | null>(null)
const rows = ref<ExecRow[]>([])
const loading = ref(false)
const filter = ref('')

const resultDialog = ref(false)
const current = ref<ExecRow | null>(null)
const form = reactive({ status: 'fail', duration_s: 120, actual_result: '', error_signature: '' })

async function load() {
  loading.value = true
  try {
    const [p, list] = await Promise.all([
      planApi.detail(planId),
      planApi.executions(planId, filter.value ? { status: filter.value } : {}),
    ])
    plan.value = p
    rows.value = list
  } finally {
    loading.value = false
  }
}

onMounted(load)

const stats = computed(() => plan.value?.stats)

async function quick(row: ExecRow, status: 'pass' | 'blocked' | 'skip') {
  if (!auth.canExecute) return
  await planApi.submitExecution(planId, { case_id: row.case_id, status, duration_s: row.duration_s ?? 60, actual_result: '' })
  await load()
}

function openResult(row: ExecRow) {
  current.value = row
  Object.assign(form, {
    status: 'fail',
    duration_s: row.duration_s ?? 120,
    actual_result: row.actual_result ?? '',
    error_signature: row.error_signature ?? '',
  })
  resultDialog.value = true
}

async function submitResult() {
  if (!current.value) return
  await planApi.submitExecution(planId, {
    case_id: current.value.case_id,
    status: form.status,
    duration_s: form.duration_s,
    actual_result: form.actual_result,
    error_signature: form.error_signature,
  })
  ElMessage.success('已记录')
  resultDialog.value = false
  await load()
}

async function finish() {
  await planApi.update(planId, { status: 'completed' })
  ElMessage.success('批次已标记完成')
  await load()
}

function exportResult() {
  window.open(planApi.exportUrl(planId), '_blank')
}

const statusText: Record<string, string> = { pass: '通过', fail: '失败', blocked: '阻塞', skip: '跳过', not_run: '未执行' }
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <el-button text size="small" @click="router.push('/plans')">← 返回批次列表</el-button>
      <div class="spacer" />
      <el-button size="small" @click="exportResult">导出结果</el-button>
      <el-button v-if="auth.canWrite && plan?.status !== 'completed'" size="small" type="primary" @click="finish">
        标记完成
      </el-button>
    </div>

    <div class="card" style="margin-bottom: 16px">
      <div class="card-head" style="margin-bottom: 8px">
        <h3 class="mono">{{ plan?.code }}</h3>
        <span class="pill" :class="plan?.status === 'running' ? 'pill-p2' : 'pill-pass'">{{ plan?.status }}</span>
        <span class="muted" style="font-size: 12.5px">{{ plan?.name }}</span>
        <div class="spacer" />
        <span class="muted" style="font-size: 12.5px">固件 {{ plan?.fw_version }} · {{ plan?.device_model }} · {{ plan?.device_sn }}</span>
      </div>

      <div class="grid grid-4" style="margin-top: 12px">
        <div class="stat" style="border: none; padding: 6px 0">
          <div class="label">执行率</div>
          <div class="value num">{{ stats?.exec_rate ?? 0 }}<small>%</small></div>
        </div>
        <div class="stat" style="border: none; padding: 6px 0">
          <div class="label">通过率</div>
          <div class="value num ok">{{ stats?.pass_rate ?? 0 }}<small>%</small></div>
        </div>
        <div class="stat" style="border: none; padding: 6px 0">
          <div class="label">失败 / 阻塞</div>
          <div class="value num"><span class="bad">{{ stats?.failed ?? 0 }}</span> <small>/ {{ stats?.blocked ?? 0 }}</small></div>
        </div>
        <div class="stat" style="border: none; padding: 6px 0">
          <div class="label">P0 阻塞</div>
          <div class="value num" :class="(stats?.p0_failed ?? 0) ? 'bad' : 'ok'">{{ stats?.p0_failed ?? 0 }}</div>
        </div>
      </div>
    </div>

    <div class="toolbar">
      <el-radio-group v-model="filter" size="small" @change="load">
        <el-radio-button value="">全部</el-radio-button>
        <el-radio-button value="not_run">未执行</el-radio-button>
        <el-radio-button value="fail">失败</el-radio-button>
        <el-radio-button value="pass">通过</el-radio-button>
        <el-radio-button value="blocked">阻塞</el-radio-button>
      </el-radio-group>
      <div class="spacer" />
      <el-button size="small" @click="load">刷新</el-button>
    </div>

    <div class="card" style="padding: 0">
      <el-table :data="rows" size="small" row-key="id">
        <el-table-column label="用例" min-width="320">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 8px">
              <span class="mono muted">{{ row.case_code }}</span>
              <span class="pill" :class="`pill-${row.priority.toLowerCase()}`">{{ row.priority }}</span>
            </div>
            <div style="margin-top: 2px">{{ row.case_title }}</div>
          </template>
        </el-table-column>
        <el-table-column prop="module_name" label="模块" width="100" />
        <el-table-column label="结果" width="110">
          <template #default="{ row }">
            <span class="pill" :class="`pill-${row.status}`">{{ statusText[row.status] }}</span>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="90">
          <template #default="{ row }">
            <span v-if="row.source === 'automation'" class="pill pill-auto">自动化</span>
            <span v-else class="muted" style="font-size: 12px">手工</span>
          </template>
        </el-table-column>
        <el-table-column label="错误特征" min-width="260">
          <template #default="{ row }">
            <span v-if="row.error_signature" class="mono muted" style="font-size: 11.5px" :title="row.error_signature">
              {{ row.error_signature.slice(0, 70) }}{{ row.error_signature.length > 70 ? '…' : '' }}
            </span>
            <span v-else class="muted">—</span>
          </template>
        </el-table-column>
        <el-table-column prop="attempts" label="尝试" width="70" />
        <el-table-column label="操作" width="240" fixed="right">
          <template #default="{ row }">
            <template v-if="auth.canExecute">
              <el-button text size="small" type="success" @click="quick(row, 'pass')">通过</el-button>
              <el-button text size="small" type="danger" @click="openResult(row)">失败</el-button>
              <el-button text size="small" @click="quick(row, 'blocked')">阻塞</el-button>
            </template>
            <span v-else class="muted" style="font-size: 12px">只读</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="resultDialog" title="记录失败详情" width="620px">
      <el-form label-width="88px">
        <el-form-item label="用例">
          <span class="mono">{{ current?.case_code }}</span>
          <span style="margin-left: 8px">{{ current?.case_title }}</span>
        </el-form-item>
        <el-form-item label="结果">
          <el-radio-group v-model="form.status">
            <el-radio value="fail">失败</el-radio>
            <el-radio value="blocked">阻塞</el-radio>
            <el-radio value="skip">跳过</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="耗时(s)">
          <el-input-number v-model="form.duration_s" :min="0" :step="30" />
        </el-form-item>
        <el-form-item label="实际表现">
          <el-input v-model="form.actual_result" type="textarea" :rows="2" placeholder="例：点击无响应，界面停留 5 秒后闪回" />
        </el-form-item>
        <el-form-item label="错误特征">
          <el-input
            v-model="form.error_signature"
            type="textarea"
            :rows="3"
            placeholder="粘贴 logcat / 异常栈。平台会自动归一化（抹掉时间、设备号、行号）后聚类"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="resultDialog = false">取消</el-button>
        <el-button type="primary" @click="submitResult">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
