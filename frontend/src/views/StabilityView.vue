<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { ElMessage } from 'element-plus'
import { computed, onMounted, reactive, ref } from 'vue'

import { metaApi, stabilityApi } from '@/api'
import type { ModuleInfo, StabilityRun } from '@/api/types'
import EChart from '@/components/EChart.vue'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const runs = ref<StabilityRun[]>([])
const modules = ref<ModuleInfo[]>([])
const activeId = ref('')
const loading = ref(false)

const current = computed(() => runs.value.find((r) => r.id === activeId.value) ?? null)

const dialog = ref(false)
const form = reactive({
  code: '',
  name: '',
  fw_version: '',
  device_sn: 'SN2026000123',
  start_at: '',
  end_at: '',
  planned_hours: 48,
  cycles_done: 0,
  crash_count: 0,
  anr_count: 0,
  hang_count: 0,
  reboot_count: 0,
  auto_recover_count: 0,
  manual_recover_count: 0,
  notes: '',
})

const incidentDialog = ref(false)
const incident = reactive({ incident_type: 'crash', module_id: '', description: '', recover_s: 30, recovered: true, occurred_at: '' })

async function load() {
  loading.value = true
  try {
    runs.value = await stabilityApi.list()
    if (!activeId.value && runs.value.length) activeId.value = runs.value[0].id
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  modules.value = await metaApi.modules()
  await load()
})

const typeOption = computed<EChartsOption>(() => {
  const rows = current.value?.by_type ?? []
  const colors: Record<string, string> = { crash: '#d1453b', anr: '#d08416', hang: '#8b5cf6', reboot: '#2f5fd0', disconnect: '#7b869c' }
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, itemWidth: 9, itemHeight: 9, textStyle: { fontSize: 11, color: '#7b869c' } },
    series: [
      {
        type: 'pie',
        radius: ['45%', '68%'],
        center: ['50%', '44%'],
        label: { show: false },
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        data: rows.map((r) => ({ name: r.incident_type, value: r.count, itemStyle: { color: colors[r.incident_type] ?? '#94a3b8' } })),
      },
    ],
  }
})

function openCreate() {
  const now = new Date()
  const end = new Date(now.getTime() - 3 * 24 * 3600 * 1000)
  const start = new Date(end.getTime() - 48 * 3600 * 1000)
  Object.assign(form, {
    code: `STAB-${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`,
    name: '',
    fw_version: '',
    device_sn: 'SN2026000123',
    start_at: start.toISOString().slice(0, 16),
    end_at: end.toISOString().slice(0, 16),
    planned_hours: 48,
    cycles_done: 0,
    crash_count: 0, anr_count: 0, hang_count: 0, reboot_count: 0,
    auto_recover_count: 0, manual_recover_count: 0,
    notes: '',
  })
  dialog.value = true
}

async function create() {
  if (!form.code || !form.name || !form.fw_version) {
    ElMessage.warning('编号、名称、固件版本必填')
    return
  }
  const payload = {
    ...form,
    start_at: new Date(form.start_at).toISOString(),
    end_at: new Date(form.end_at).toISOString(),
  }
  const run = await stabilityApi.create(payload)
  ElMessage.success('已创建')
  dialog.value = false
  await load()
  activeId.value = run.id
}

function openIncident() {
  incident.occurred_at = new Date().toISOString().slice(0, 16)
  incidentDialog.value = true
}

async function addIncident() {
  if (!current.value) return
  await stabilityApi.addIncident(current.value.id, {
    ...incident,
    module_id: incident.module_id || null,
    occurred_at: new Date(incident.occurred_at).toISOString(),
  })
  ElMessage.success('已追加异常明细')
  incidentDialog.value = false
  await load()
}
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <span class="muted" style="font-size: 12.5px">口径：MTBF = 运行时长 / 异常总数（crash+anr+hang+reboot）</span>
      <div class="spacer" />
      <el-button size="small" @click="load">刷新</el-button>
      <el-button v-if="auth.canWrite" type="primary" size="small" @click="openCreate">新建压测批次</el-button>
    </div>

    <div style="display: grid; grid-template-columns: 300px 1fr; gap: 16px">
      <div>
        <div
          v-for="r in runs"
          :key="r.id"
          class="card"
          style="padding: 13px 15px; cursor: pointer; margin-bottom: 10px"
          :style="r.id === activeId ? 'border-color: var(--primary); box-shadow: 0 0 0 2px var(--primary-soft)' : ''"
          @click="activeId = r.id"
        >
          <div class="mono" style="font-size: 12px; color: var(--muted)">{{ r.code }}</div>
          <div style="font-size: 13.5px; margin: 3px 0 8px">{{ r.name }}</div>
          <div style="display: flex; gap: 14px; font-size: 12px">
            <span class="muted">MTBF <b class="num" :class="(r.metrics.mtbf_hours ?? 99) >= 12 ? 'ok' : 'bad'">
              {{ r.metrics.mtbf_hours ?? '∞' }}</b> h</span>
            <span class="muted">异常 <b class="num">{{ r.metrics.total_abnormal }}</b></span>
          </div>
        </div>
      </div>

      <div v-if="current">
        <div class="grid grid-4">
          <div class="stat">
            <div class="label">运行时长</div>
            <div class="value num">{{ current.metrics.runtime_hours }}<small>h</small></div>
            <div class="foot">计划 {{ current.planned_hours }}h · 循环 {{ current.cycles_done }} 次</div>
          </div>
          <div class="stat">
            <div class="label">MTBF</div>
            <div class="value num" :class="(current.metrics.mtbf_hours ?? 99) >= 12 ? 'ok' : 'bad'">
              {{ current.metrics.mtbf_hours ?? '—' }}<small>h</small>
            </div>
            <div class="foot">平均无故障时间，越大越好</div>
          </div>
          <div class="stat">
            <div class="label">异常总数</div>
            <div class="value num bad">{{ current.metrics.total_abnormal }}</div>
            <div class="foot">
              crash {{ current.crash_count }} · anr {{ current.anr_count }} · hang {{ current.hang_count }} · reboot {{ current.reboot_count }}
            </div>
          </div>
          <div class="stat">
            <div class="label">恢复率</div>
            <div class="value num" :class="current.metrics.recovery_rate >= 90 ? 'ok' : 'warn'">
              {{ current.metrics.recovery_rate }}<small>%</small>
            </div>
            <div class="foot">
              自动 {{ current.metrics.auto_recover_ratio }}% · 平均 {{ current.metrics.avg_recover_s ?? '—' }}s
            </div>
          </div>
        </div>

        <div class="grid grid-3-2" style="margin-top: 16px">
          <div class="card">
            <div class="card-head">
              <h3>异常明细</h3>
              <span class="sub">共 {{ current.incidents.length }} 条</span>
              <div class="spacer" />
              <el-button v-if="auth.canWrite" size="small" @click="openIncident">追加明细</el-button>
            </div>
            <el-table :data="current.incidents" size="small" max-height="360">
              <el-table-column label="时间" width="140">
                <template #default="{ row }">{{ new Date(row.occurred_at).toLocaleString('zh-CN', { hour12: false }) }}</template>
              </el-table-column>
              <el-table-column prop="incident_type" label="类型" width="84">
                <template #default="{ row }">
                  <span class="pill" :class="row.incident_type === 'crash' ? 'pill-fail' : 'pill-blocked'">{{ row.incident_type }}</span>
                </template>
              </el-table-column>
              <el-table-column prop="description" label="现象" min-width="220" show-overflow-tooltip />
              <el-table-column label="恢复" width="90">
                <template #default="{ row }">
                  <span v-if="row.recovered" class="ok">{{ row.recover_s }}s</span>
                  <span v-else class="bad">需人工</span>
                </template>
              </el-table-column>
            </el-table>
          </div>

          <div class="card">
            <div class="card-head"><h3>异常类型分布</h3></div>
            <EChart :option="typeOption" :height="300" />
          </div>
        </div>
      </div>
    </div>

    <el-dialog v-model="dialog" title="新建压测批次" width="640px">
      <el-form label-width="96px">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px">
          <el-form-item label="批次编号" required><el-input v-model="form.code" /></el-form-item>
          <el-form-item label="固件版本" required><el-input v-model="form.fw_version" placeholder="1.3.1.0" /></el-form-item>
        </div>
        <el-form-item label="名称" required><el-input v-model="form.name" placeholder="1.3.1.0 连续 48 小时稳定性" /></el-form-item>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px">
          <el-form-item label="开始时间"><el-date-picker v-model="form.start_at" type="datetime" style="width: 100%" /></el-form-item>
          <el-form-item label="结束时间"><el-date-picker v-model="form.end_at" type="datetime" style="width: 100%" /></el-form-item>
          <el-form-item label="计划时长"><el-input-number v-model="form.planned_hours" :min="1" /> </el-form-item>
          <el-form-item label="循环次数"><el-input-number v-model="form.cycles_done" :min="0" /></el-form-item>
          <el-form-item label="crash"><el-input-number v-model="form.crash_count" :min="0" /></el-form-item>
          <el-form-item label="anr"><el-input-number v-model="form.anr_count" :min="0" /></el-form-item>
          <el-form-item label="hang"><el-input-number v-model="form.hang_count" :min="0" /></el-form-item>
          <el-form-item label="reboot"><el-input-number v-model="form.reboot_count" :min="0" /></el-form-item>
          <el-form-item label="自动恢复"><el-input-number v-model="form.auto_recover_count" :min="0" /></el-form-item>
          <el-form-item label="人工恢复"><el-input-number v-model="form.manual_recover_count" :min="0" /></el-form-item>
        </div>
        <el-form-item label="备注"><el-input v-model="form.notes" type="textarea" :rows="2" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="incidentDialog" title="追加异常明细" width="560px">
      <el-form label-width="88px">
        <el-form-item label="类型">
          <el-select v-model="incident.incident_type" style="width: 100%">
            <el-option label="crash 崩溃" value="crash" />
            <el-option label="anr 无响应" value="anr" />
            <el-option label="hang 卡死" value="hang" />
            <el-option label="reboot 重启" value="reboot" />
            <el-option label="disconnect 断连" value="disconnect" />
          </el-select>
        </el-form-item>
        <el-form-item label="模块">
          <el-select v-model="incident.module_id" clearable style="width: 100%">
            <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="发生时间">
          <el-date-picker v-model="incident.occurred_at" type="datetime" style="width: 100%" />
        </el-form-item>
        <el-form-item label="现象"><el-input v-model="incident.description" /></el-form-item>
        <el-form-item label="恢复耗时"><el-input-number v-model="incident.recover_s" :min="0" /> 秒</el-form-item>
        <el-form-item label="已恢复"><el-switch v-model="incident.recovered" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="incidentDialog = false">取消</el-button>
        <el-button type="primary" @click="addIncident">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
