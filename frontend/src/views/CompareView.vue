<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { planApi, reportApi } from '@/api'
import type { CompareResult, PlanInfo } from '@/api/types'

const plans = ref<PlanInfo[]>([])
const baseId = ref('')
const targetId = ref('')
const result = ref<CompareResult | null>(null)
const loading = ref(false)
const tab = ref('new_fail')

async function load() {
  plans.value = (await planApi.list({ size: 50 })).items
  if (plans.value.length >= 2) {
    targetId.value = plans.value[0].id
    baseId.value = plans.value[1].id
    await run()  // 默认就选最近两版并跑一次，进来就能看到 diff
  }
}

onMounted(load)

async function run() {
  if (!baseId.value || !targetId.value) return
  loading.value = true
  try {
    result.value = await reportApi.compare(baseId.value, targetId.value)
  } finally {
    loading.value = false
  }
}

const statusText: Record<string, string> = { pass: '通过', fail: '失败', blocked: '阻塞', not_run: '未执行', skip: '跳过', absent: '不存在' }
</script>

<template>
  <div>
    <div class="card">
      <div class="card-head">
        <h3>选择两个批次做回归对比</h3>
        <span class="sub">基准 = 上一版，对比 = 本版</span>
      </div>
      <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap">
        <el-select v-model="baseId" placeholder="基准批次" style="width: 260px">
          <el-option v-for="p in plans" :key="p.id" :label="`${p.code} · ${p.fw_version}`" :value="p.id" />
        </el-select>
        <span class="muted">→</span>
        <el-select v-model="targetId" placeholder="对比批次" style="width: 260px">
          <el-option v-for="p in plans" :key="p.id" :label="`${p.code} · ${p.fw_version}`" :value="p.id" />
        </el-select>
        <el-button type="primary" :loading="loading" @click="run">开始对比</el-button>
      </div>
    </div>

    <template v-if="result">
      <div class="grid grid-4" style="margin-top: 16px">
        <div class="stat">
          <div class="label">新增失败</div>
          <div class="value num bad">{{ result.new_fail.length }}</div>
          <div class="foot">上一版通过，本版失败 —— 回归风险</div>
        </div>
        <div class="stat">
          <div class="label">已修复</div>
          <div class="value num ok">{{ result.fixed.length }}</div>
          <div class="foot">上一版失败，本版通过</div>
        </div>
        <div class="stat">
          <div class="label">仍未修复</div>
          <div class="value num warn">{{ result.still_fail.length }}</div>
          <div class="foot">连续两版失败，需跟踪责任人</div>
        </div>
        <div class="stat">
          <div class="label">新增 / 移除用例</div>
          <div class="value num">{{ result.new_case.length }} <small>/ {{ result.removed.length }}</small></div>
          <div class="foot">用例范围变化说明</div>
        </div>
      </div>

      <div class="card" style="margin-top: 16px">
        <el-tabs v-model="tab">
          <el-tab-pane :label="`新增失败 (${result.new_fail.length})`" name="new_fail" />
          <el-tab-pane :label="`已修复 (${result.fixed.length})`" name="fixed" />
          <el-tab-pane :label="`仍未修复 (${result.still_fail.length})`" name="still_fail" />
          <el-tab-pane :label="`新增用例 (${result.new_case.length})`" name="new_case" />
          <el-tab-pane :label="`已移除 (${result.removed.length})`" name="removed" />
        </el-tabs>

        <el-table :data="result[tab as keyof CompareResult] as any[]" size="small" empty-text="没有差异，这一项为空">
          <el-table-column label="用例" min-width="320">
            <template #default="{ row }">
              <div style="display: flex; align-items: center; gap: 8px">
                <span class="mono muted">{{ row.case_code }}</span>
                <span class="pill" :class="`pill-${row.priority.toLowerCase()}`">{{ row.priority }}</span>
                <span class="muted" style="font-size: 12px">{{ row.module_name }}</span>
              </div>
              <div style="margin-top: 2px">{{ row.case_title }}</div>
            </template>
          </el-table-column>
          <el-table-column label="基准批次" width="120">
            <template #default="{ row }">
              <span class="pill" :class="`pill-${row.base_status}`">{{ statusText[row.base_status] ?? row.base_status }}</span>
            </template>
          </el-table-column>
          <el-table-column label="对比批次" width="120">
            <template #default="{ row }">
              <span class="pill" :class="`pill-${row.target_status}`">{{ statusText[row.target_status] ?? row.target_status }}</span>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <div class="muted" style="margin-top: 12px; font-size: 12px">
        对比基于用例 ID 对齐：{{ result.base_plan.code }}（{{ result.base_plan.fw_version }}）→
        {{ result.target_plan.code }}（{{ result.target_plan.fw_version }}）
      </div>
    </template>

    <div v-else class="card" style="margin-top: 16px">
      <div class="empty">选择两个批次后点击「开始对比」</div>
    </div>
  </div>
</template>
