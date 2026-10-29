<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, ref } from 'vue'

import { automationApi, planApi } from '@/api'
import type { AutomationRun, PlanInfo } from '@/api/types'

const runs = ref<AutomationRun[]>([])
const plans = ref<PlanInfo[]>([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const [r, p] = await Promise.all([automationApi.runs(), planApi.list({ size: 50 })])
    runs.value = r
    plans.value = p.items
  } finally {
    loading.value = false
  }
}

onMounted(load)

const curl = `# 脚本跑完后把结果推上来，平台负责算聚类键与统计
curl -X POST http://127.0.0.1:8000/api/v1/automation/runs \\
  -H "Content-Type: application/json" \\
  -H "X-Automation-Token: dev-automation-token" \\
  -d '{
    "plan_code": "R2026.10-W3",
    "script_name": "appium_navi_smoke.py",
    "device_sn": "SN2026000123",
    "started_at": "2026-10-29T10:00:00Z",
    "results": [
      {"case_code": "NAVI-001", "status": "pass", "duration_s": 62},
      {"case_code": "NAVI-002", "status": "fail", "duration_s": 88,
       "error_text": "com.amap.api.services.core.AMapException: 网络请求失败, code=12"}
    ]
  }'`

const pythonSnippet = `# pytest 结束后在 conftest 里一次性上报
def report_results(plan_code: str, items: list[dict]) -> None:
    requests.post(
        "http://127.0.0.1:8000/api/v1/automation/runs",
        headers={"X-Automation-Token": os.environ["AUTOMATION_TOKEN"]},
        json={
            "plan_code": plan_code,
            "script_name": "appium_navi_smoke.py",
            "device_sn": os.environ.get("DEVICE_SN", ""),
            "started_at": STARTED_AT.isoformat(),
            "results": items,   # [{"case_code","status","duration_s","error_text"}]
        },
        timeout=20,
    )`

async function copy(text: string) {
  await navigator.clipboard.writeText(text)
  ElMessage.success('已复制')
}
</script>

<template>
  <div>
    <div class="grid grid-3-2">
      <div class="card">
        <div class="card-head">
          <h3>回传接口</h3>
          <span class="sub">POST /api/v1/automation/runs</span>
          <div class="spacer" />
          <el-button size="small" @click="copy(curl)">复制 curl</el-button>
        </div>
        <pre class="mono" style="background: #0f1725; color: #cfe0f5; padding: 14px; border-radius: 9px; overflow: auto; font-size: 11.5px; line-height: 1.7; margin: 0">{{ curl }}</pre>

        <div class="card-head" style="margin-top: 18px">
          <h3>pytest 里怎么接</h3>
          <div class="spacer" />
          <el-button size="small" @click="copy(pythonSnippet)">复制 Python</el-button>
        </div>
        <pre class="mono" style="background: #f7f9fc; border: 1px solid var(--line); padding: 14px; border-radius: 9px; overflow: auto; font-size: 11.5px; line-height: 1.7; margin: 0">{{ pythonSnippet }}</pre>
      </div>

      <div class="card">
        <div class="card-head"><h3>设计说明</h3></div>
        <div style="font-size: 13px; line-height: 2; color: #46506a">
          <p style="margin: 0 0 10px">
            <b>为什么用静态令牌而不是 JWT：</b>CI 里不该保存某个人的账号密码，脚本是服务身份，令牌可以独立吊销与轮换。
          </p>
          <p style="margin: 0 0 10px">
            <b>为什么只传用例编号：</b>脚本不该关心用例 ID、计划 ID 这些内部主键，编号是人对人也对机器的稳定契约。
          </p>
          <p style="margin: 0 0 10px">
            <b>为什么手工和自动化进同一张表：</b>回归对比、聚类、看板都要看「这个用例最终是什么结果」，分两张表会让统计口径分裂。
          </p>
          <p style="margin: 0">
            <b>幂等性：</b>(plan_id, case_id) 唯一，重复上报是覆盖 + attempts 累加，脚本重跑不会产生脏数据。
          </p>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top: 16px">
      <div class="card-head">
        <h3>最近回传记录</h3>
        <span class="sub">{{ runs.length }} 次</span>
        <div class="spacer" />
        <el-button size="small" @click="load">刷新</el-button>
      </div>
      <el-table v-loading="loading" :data="runs" size="small">
        <el-table-column prop="script_name" label="脚本" min-width="200">
          <template #default="{ row }"><span class="mono">{{ row.script_name }}</span></template>
        </el-table-column>
        <el-table-column label="批次" width="150">
          <template #default="{ row }">
            <span class="mono muted">{{ plans.find((p) => p.id === row.plan_id)?.code ?? '—' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="device_sn" label="设备" width="150" />
        <el-table-column label="结果" width="220">
          <template #default="{ row }">
            <span class="ok">{{ row.passed }} 通过</span> ·
            <span class="bad">{{ row.failed }} 失败</span> ·
            <span class="muted">{{ row.skipped }} 跳过</span>
          </template>
        </el-table-column>
        <el-table-column label="开始时间" width="170">
          <template #default="{ row }">{{ new Date(row.started_at).toLocaleString('zh-CN', { hour12: false }) }}</template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>
