<script setup lang="ts">
import type { EChartsOption } from 'echarts'
import { computed, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { planApi, reportApi } from '@/api'
import type { Dashboard, PlanInfo } from '@/api/types'
import EChart from '@/components/EChart.vue'

const router = useRouter()
const loading = ref(false)
const data = ref<Dashboard | null>(null)
const plans = ref<PlanInfo[]>([])
const planId = ref<string>('')

const stats = computed(() => data.value?.stats)

async function load() {
  loading.value = true
  try {
    data.value = await reportApi.dashboard(planId.value || undefined)
    if (!planId.value && data.value?.plan_id) planId.value = data.value.plan_id
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  plans.value = (await planApi.list({ size: 50 })).items
  await load()
})

watch(planId, load)

const moduleOption = computed<EChartsOption>(() => {
  const rows = data.value?.by_module ?? []
  return {
    grid: { left: 8, right: 16, top: 28, bottom: 4, containLabel: true },
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { data: ['通过', '失败', '未执行'], right: 0, top: 0, itemWidth: 9, itemHeight: 9, textStyle: { fontSize: 11, color: '#7b869c' } },
    xAxis: { type: 'category', data: rows.map((r) => r.module_name), axisLine: { lineStyle: { color: '#e3e8f2' } }, axisLabel: { color: '#7b869c', fontSize: 11 }, axisTick: { show: false } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#f0f3f8' } }, axisLabel: { color: '#7b869c', fontSize: 11 } },
    series: [
      { name: '通过', type: 'bar', stack: 'a', barWidth: 22, itemStyle: { color: '#12996a', borderRadius: [0, 0, 0, 0] }, data: rows.map((r) => r.passed) },
      { name: '失败', type: 'bar', stack: 'a', itemStyle: { color: '#d1453b' }, data: rows.map((r) => r.failed) },
      { name: '未执行', type: 'bar', stack: 'a', itemStyle: { color: '#dfe4ee', borderRadius: [3, 3, 0, 0] }, data: rows.map((r) => r.total - r.executed) },
    ],
  }
})

const donutOption = computed<EChartsOption>(() => {
  const s = stats.value
  const rows = [
    { name: '通过', value: s?.passed ?? 0, color: '#12996a' },
    { name: '失败', value: s?.failed ?? 0, color: '#d1453b' },
    { name: '阻塞', value: s?.blocked ?? 0, color: '#d08416' },
    { name: '未执行', value: s?.not_run ?? 0, color: '#dfe4ee' },
  ]
  return {
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', right: 0, top: 'center', itemWidth: 9, itemHeight: 9, textStyle: { fontSize: 12, color: '#5b6478' } },
    series: [
      {
        type: 'pie',
        radius: ['52%', '74%'],
        center: ['36%', '50%'],
        avoidLabelOverlap: true,
        itemStyle: { borderColor: '#fff', borderWidth: 2 },
        label: { show: false },
        data: rows.map((r) => ({ name: r.name, value: r.value, itemStyle: { color: r.color } })),
      },
    ],
  }
})

const trendOption = computed<EChartsOption>(() => {
  const rows = data.value?.trend ?? []
  return {
    grid: { left: 8, right: 16, top: 20, bottom: 4, containLabel: true },
    tooltip: {
      trigger: 'axis',
      formatter: (params: any) => {
        const i = params[0].dataIndex
        const r = rows[i]
        return `${r.plan_code}<br/>固件 ${r.fw_version}<br/>通过率 <b>${r.pass_rate}%</b>　失败 ${r.failed}`
      },
    },
    xAxis: {
      type: 'category',
      data: rows.map((r) => r.plan_code.replace('R', '')),
      axisLabel: { fontSize: 10.5, color: '#7b869c', hideOverlap: true },
      axisLine: { lineStyle: { color: '#e3e8f2' } },
      axisTick: { show: false },
    },
    yAxis: { type: 'value', max: 100, axisLabel: { formatter: '{value}%', color: '#7b869c', fontSize: 11 }, splitLine: { lineStyle: { color: '#f0f3f8' } } },
    series: [
      {
        type: 'line',
        smooth: true,
        symbolSize: 7,
        data: rows.map((r) => r.pass_rate),
        itemStyle: { color: '#2f5fd0' },
        lineStyle: { width: 2.4 },
        areaStyle: { color: 'rgba(47,95,208,0.10)' },
        label: { show: true, formatter: '{c}%', fontSize: 11, color: '#2f5fd0', position: 'top' },
      },
    ],
  }
})

const statusText: Record<string, string> = { pass: '通过', fail: '失败', blocked: '阻塞', not_run: '未执行', skip: '跳过' }
</script>

<template>
  <div v-loading="loading">
    <div class="toolbar">
      <el-select v-model="planId" placeholder="选择批次" style="width: 280px">
        <el-option v-for="p in plans" :key="p.id" :label="`${p.code} · ${p.fw_version}`" :value="p.id" />
      </el-select>
      <span class="muted" style="font-size: 12.5px">
        设备 {{ plans.find((p) => p.id === planId)?.device_model }} ·
        {{ plans.find((p) => p.id === planId)?.device_sn || '未绑定' }}
      </span>
      <div class="spacer" />
      <el-button v-if="planId" size="small" @click="router.push(`/plans/${planId}`)">进入执行清单</el-button>
      <el-button size="small" @click="load">刷新</el-button>
    </div>

    <div class="grid grid-4">
      <div class="stat">
        <div class="label">执行进度</div>
        <div class="value num">{{ stats?.exec_rate ?? 0 }}<small>%</small></div>
        <div class="foot">已执行 {{ stats?.total ? stats.total - stats.not_run : 0 }} / {{ stats?.total ?? 0 }} 条</div>
      </div>
      <div class="stat">
        <div class="label">通过率</div>
        <div class="value num" :class="(stats?.pass_rate ?? 0) >= 85 ? 'ok' : 'warn'">
          {{ stats?.pass_rate ?? 0 }}<small>%</small>
        </div>
        <div class="foot">通过 {{ stats?.passed ?? 0 }} · 失败 {{ stats?.failed ?? 0 }}</div>
      </div>
      <div class="stat">
        <div class="label">P0 阻塞项</div>
        <div class="value num" :class="(stats?.p0_failed ?? 0) > 0 ? 'bad' : 'ok'">{{ stats?.p0_failed ?? 0 }}</div>
        <div class="foot">P0 用例失败数，需优先处理</div>
      </div>
      <div class="stat">
        <div class="label">失败簇</div>
        <div class="value num">{{ data?.top_clusters.length ?? 0 }}</div>
        <div class="foot">按根因归一化后的聚类数</div>
      </div>
    </div>

    <div class="grid grid-3-2" style="margin-top: 16px">
      <div class="card">
        <div class="card-head">
          <h3>各模块执行分布</h3>
          <span class="sub">{{ data?.plan_code }} · {{ data?.fw_version }}</span>
        </div>
        <EChart :option="moduleOption" :height="280" />
      </div>

      <div class="card">
        <div class="card-head"><h3>结果构成</h3></div>
        <EChart :option="donutOption" :height="280" />
      </div>
    </div>

    <div class="grid grid-2" style="margin-top: 16px">
      <div class="card">
        <div class="card-head">
          <h3>批次通过率走势</h3>
          <span class="sub">最近 {{ data?.trend.length ?? 0 }} 个批次</span>
        </div>
        <EChart :option="trendOption" :height="250" />
      </div>

      <div class="card">
        <div class="card-head">
          <h3>失败聚类 TOP</h3>
          <span class="sub">同一根因合并计数</span>
        </div>
        <div v-if="!data?.top_clusters.length" class="empty">本批次暂无失败</div>
        <div v-for="(c, i) in data?.top_clusters ?? []" :key="c.cluster_key" style="padding: 9px 0; border-bottom: 1px dashed var(--line)">
          <div style="display: flex; align-items: center; gap: 8px">
            <span class="pill" :class="i === 0 ? 'pill-fail' : 'pill-p2'">{{ c.count }} 条</span>
            <span class="mono" style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap" :title="c.cluster_key">
              {{ c.cluster_key || '未填写错误特征' }}
            </span>
          </div>
          <div class="muted" style="font-size: 12px; margin-top: 5px">
            {{ c.module_names.join(' / ') }} · {{ c.case_codes.slice(0, 6).join('、') }}
          </div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top: 16px">
      <div class="card-head">
        <h3>优先级维度</h3>
        <span class="sub">P0 不通过即视为阻塞发版</span>
      </div>
      <el-table :data="data?.by_priority ?? []" size="small">
        <el-table-column label="优先级" width="110">
          <template #default="{ row }">
            <span class="pill" :class="`pill-${row.priority.toLowerCase()}`">{{ row.priority }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="total" label="用例数" width="100" />
        <el-table-column prop="passed" label="通过" width="100" />
        <el-table-column prop="failed" label="失败" width="100" />
        <el-table-column label="通过率" min-width="200">
          <template #default="{ row }">
            <div style="display: flex; align-items: center; gap: 10px">
              <div class="progress-line" style="flex: 1">
                <i :style="{ width: `${row.pass_rate}%`, background: row.pass_rate >= 85 ? 'var(--ok)' : 'var(--bad)' }" />
              </div>
              <span class="num" style="font-size: 12.5px; width: 50px">{{ row.pass_rate }}%</span>
            </div>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="muted" style="margin-top: 14px; font-size: 12px">
      口径说明：通过率分母为「已执行且非跳过」的用例数；{{ statusText.not_run }}的用例不计入通过率，避免把没跑当成失败。
    </div>
  </div>
</template>
