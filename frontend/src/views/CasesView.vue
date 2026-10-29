<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref, watch } from 'vue'

import { caseApi, metaApi } from '@/api'
import type { CaseInfo, ModuleInfo } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const modules = ref<ModuleInfo[]>([])
const rows = ref<CaseInfo[]>([])
const total = ref(0)
const loading = ref(false)

const query = reactive({ q: '', module_id: '', priority: '', status: 'active', page: 1, size: 15 })

const detail = ref<CaseInfo | null>(null)
const drawer = ref(false)

const editor = ref(false)
const editing = ref<CaseInfo | null>(null)
const form = reactive({
  code: '',
  title: '',
  module_id: '',
  priority: 'P1',
  case_type: 'function',
  precondition: '',
  expected: '',
  tags: '',
  status: 'active',
  steps: [{ action: '', expected: '' }],
})

const moduleName = (id: string) => modules.value.find((m) => m.id === id)?.name ?? '—'

async function load() {
  loading.value = true
  try {
    const data = await caseApi.list({ ...query, module_id: query.module_id || undefined, priority: query.priority || undefined })
    rows.value = data.items
    total.value = data.total
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  modules.value = await metaApi.modules()
  await load()
})

watch(() => [query.module_id, query.priority, query.status, query.page], load)

function openDetail(row: CaseInfo) {
  detail.value = row
  drawer.value = true
}

function openCreate() {
  editing.value = null
  Object.assign(form, {
    code: '', title: '', module_id: modules.value[0]?.id ?? '', priority: 'P1',
    case_type: 'function', precondition: '', expected: '', tags: '', status: 'active',
    steps: [{ action: '', expected: '' }],
  })
  editor.value = true
}

function openEdit(row: CaseInfo) {
  editing.value = row
  Object.assign(form, {
    code: row.code,
    title: row.title,
    module_id: row.module_id,
    priority: row.priority,
    case_type: row.case_type,
    precondition: row.precondition,
    expected: row.expected,
    tags: (row.tags ?? []).join(','),
    status: row.status,
    steps: row.steps?.length ? row.steps.map((s) => ({ action: s.action, expected: s.expected })) : [{ action: '', expected: '' }],
  })
  editor.value = true
}

async function save() {
  if (!form.code || !form.title || !form.module_id) {
    ElMessage.warning('用例编号、标题、模块为必填')
    return
  }
  const payload: Partial<CaseInfo> = {
    code: form.code,
    title: form.title,
    module_id: form.module_id,
    priority: form.priority as CaseInfo['priority'],
    case_type: form.case_type,
    precondition: form.precondition,
    expected: form.expected,
    status: form.status,
    tags: form.tags.split(/[,，]/).map((t) => t.trim()).filter(Boolean),
    steps: form.steps
      .filter((s) => s.action || s.expected)
      .map((s, i) => ({ no: i + 1, action: s.action, expected: s.expected })),
  }
  if (editing.value) {
    await caseApi.update(editing.value.id, payload)
    ElMessage.success('已更新')
  } else {
    await caseApi.create(payload)
    ElMessage.success('已创建')
  }
  editor.value = false
  await load()
}

async function deprecate(row: CaseInfo) {
  await ElMessageBox.confirm(`确认废弃 ${row.code}？历史批次记录仍会保留。`, '废弃用例', { type: 'warning' })
  await caseApi.deprecate(row.id)
  ElMessage.success('已废弃')
  await load()
}

const importVisible = ref(false)
const importResult = ref<{ created: number; updated: number; skipped: number; errors: { row: number; reason: string }[] } | null>(null)

async function doImport(file: File) {
  importResult.value = await caseApi.import(file)
  ElMessage.success(`导入完成：新增 ${importResult.value.created}，更新 ${importResult.value.updated}`)
  await load()
}

function downloadTemplate() {
  window.open(caseApi.templateUrl, '_blank')
}

function exportCases() {
  window.open(caseApi.exportUrl, '_blank')
}

const priorityOptions = ['P0', 'P1', 'P2', 'P3']
</script>

<template>
  <div>
    <div class="toolbar">
      <el-input v-model="query.q" placeholder="搜索编号或标题" clearable style="width: 220px" @keyup.enter="query.page = 1; load()" />
      <el-select v-model="query.module_id" placeholder="全部模块" clearable style="width: 140px">
        <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
      </el-select>
      <el-select v-model="query.priority" placeholder="全部优先级" clearable style="width: 130px">
        <el-option v-for="p in priorityOptions" :key="p" :label="p" :value="p" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable style="width: 120px">
        <el-option label="生效中" value="active" />
        <el-option label="草稿" value="draft" />
        <el-option label="已废弃" value="deprecated" />
      </el-select>
      <el-button @click="query.page = 1; load()">查询</el-button>
      <div class="spacer" />
      <el-button v-if="auth.canWrite" @click="importVisible = true">批量导入</el-button>
      <el-button @click="exportCases">导出</el-button>
      <el-button v-if="auth.canWrite" type="primary" @click="openCreate">新建用例</el-button>
    </div>

    <div class="card" style="padding: 0">
      <el-table v-loading="loading" :data="rows" size="small" @row-click="openDetail">
        <el-table-column prop="code" label="编号" width="120">
          <template #default="{ row }"><span class="mono">{{ row.code }}</span></template>
        </el-table-column>
        <el-table-column prop="title" label="用例标题" min-width="300" show-overflow-tooltip />
        <el-table-column label="模块" width="110">
          <template #default="{ row }">{{ moduleName(row.module_id) }}</template>
        </el-table-column>
        <el-table-column label="优先级" width="90">
          <template #default="{ row }">
            <span class="pill" :class="`pill-${row.priority.toLowerCase()}`">{{ row.priority }}</span>
          </template>
        </el-table-column>
        <el-table-column label="步骤" width="70">
          <template #default="{ row }">{{ row.steps?.length ?? 0 }}</template>
        </el-table-column>
        <el-table-column label="标签" min-width="160">
          <template #default="{ row }">
            <el-tag v-for="t in row.tags" :key="t" size="small" effect="plain" style="margin-right: 4px">{{ t }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="90">
          <template #default="{ row }">
            <span class="pill" :class="row.status === 'active' ? 'pill-pass' : 'pill-skip'">
              {{ row.status === 'active' ? '生效' : row.status === 'draft' ? '草稿' : '废弃' }}
            </span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="130" fixed="right">
          <template #default="{ row }">
            <el-button v-if="auth.canWrite" text size="small" @click.stop="openEdit(row)">编辑</el-button>
            <el-button v-if="auth.canWrite" text size="small" type="danger" @click.stop="deprecate(row)">废弃</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div style="display: flex; justify-content: flex-end; padding: 12px 16px">
        <el-pagination
          v-model:current-page="query.page"
          :page-size="query.size"
          :total="total"
          layout="total, prev, pager, next"
          background
        />
      </div>
    </div>

    <el-drawer v-model="drawer" title="用例详情" size="520px">
      <template v-if="detail">
        <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 6px">
          <span class="mono">{{ detail.code }}</span>
          <span class="pill" :class="`pill-${detail.priority.toLowerCase()}`">{{ detail.priority }}</span>
          <span class="muted" style="font-size: 12px">{{ moduleName(detail.module_id) }}</span>
        </div>
        <h3 style="margin: 6px 0 16px; font-size: 16px">{{ detail.title }}</h3>

        <el-descriptions :column="1" border size="small">
          <el-descriptions-item label="前置条件">{{ detail.precondition || '—' }}</el-descriptions-item>
          <el-descriptions-item label="预期结果">{{ detail.expected || '—' }}</el-descriptions-item>
          <el-descriptions-item label="标签">
            <el-tag v-for="t in detail.tags" :key="t" size="small" effect="plain" style="margin-right: 4px">{{ t }}</el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="备注">{{ detail.remark || '—' }}</el-descriptions-item>
        </el-descriptions>

        <h4 style="margin: 20px 0 10px; font-size: 13px">操作步骤</h4>
        <el-table :data="detail.steps" size="small" border>
          <el-table-column prop="no" label="#" width="46" />
          <el-table-column prop="action" label="操作" />
          <el-table-column prop="expected" label="预期" />
        </el-table>
      </template>
    </el-drawer>

    <el-dialog v-model="editor" :title="editing ? '编辑用例' : '新建用例'" width="720px">
      <el-form label-width="82px" label-position="right">
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px">
          <el-form-item label="用例编号" required>
            <el-input v-model="form.code" :disabled="Boolean(editing)" placeholder="VOICE-101" />
          </el-form-item>
          <el-form-item label="模块" required>
            <el-select v-model="form.module_id" style="width: 100%">
              <el-option v-for="m in modules" :key="m.id" :label="m.name" :value="m.id" />
            </el-select>
          </el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority" style="width: 100%">
              <el-option v-for="p in priorityOptions" :key="p" :label="p" :value="p" />
            </el-select>
          </el-form-item>
          <el-form-item label="用例类型">
            <el-select v-model="form.case_type" style="width: 100%">
              <el-option label="功能" value="function" />
              <el-option label="性能" value="performance" />
              <el-option label="稳定性" value="stability" />
              <el-option label="兼容性" value="compatibility" />
            </el-select>
          </el-form-item>
        </div>
        <el-form-item label="标题" required>
          <el-input v-model="form.title" placeholder="一句话说明验证点" />
        </el-form-item>
        <el-form-item label="前置条件">
          <el-input v-model="form.precondition" type="textarea" :rows="2" />
        </el-form-item>

        <el-form-item label="步骤">
          <div style="width: 100%">
            <div v-for="(s, i) in form.steps" :key="i" style="display: flex; gap: 8px; margin-bottom: 8px">
              <span class="muted" style="width: 18px; line-height: 30px">{{ i + 1 }}</span>
              <el-input v-model="s.action" placeholder="操作" />
              <el-input v-model="s.expected" placeholder="预期" />
              <el-button text type="danger" @click="form.steps.splice(i, 1)">删</el-button>
            </div>
            <el-button size="small" @click="form.steps.push({ action: '', expected: '' })">+ 添加步骤</el-button>
          </div>
        </el-form-item>

        <el-form-item label="预期结果">
          <el-input v-model="form.expected" type="textarea" :rows="2" />
        </el-form-item>
        <el-form-item label="标签">
          <el-input v-model="form.tags" placeholder="英文逗号分隔，如 冒烟,联动" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="editor = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="批量导入用例" width="560px">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 14px">
        <template #title>
          按模板填写后导入。编号已存在则更新（覆盖字段），模块编码必须已存在。
        </template>
      </el-alert>
      <el-button size="small" @click="downloadTemplate">下载导入模板</el-button>
      <el-upload
        drag
        :auto-upload="false"
        :show-file-list="false"
        accept=".xlsx"
        style="margin-top: 14px"
        :on-change="(f: any) => doImport(f.raw as File)"
      >
        <div style="padding: 20px; color: var(--muted); font-size: 13px">把 .xlsx 拖到这里，或点击选择文件</div>
      </el-upload>
      <div v-if="importResult" style="margin-top: 14px">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="新增">{{ importResult.created }}</el-descriptions-item>
          <el-descriptions-item label="更新">{{ importResult.updated }}</el-descriptions-item>
          <el-descriptions-item label="跳过">{{ importResult.skipped }}</el-descriptions-item>
        </el-descriptions>
        <div v-if="importResult.errors.length" style="margin-top: 10px">
          <div class="bad" style="font-size: 13px; margin-bottom: 6px">{{ importResult.errors.length }} 行有错误</div>
          <div v-for="e in importResult.errors" :key="e.row" class="mono muted">第 {{ e.row }} 行：{{ e.reason }}</div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>
