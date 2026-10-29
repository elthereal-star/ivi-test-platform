<script setup lang="ts">
import { ElMessage } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { aiApi, metaApi } from '@/api'
import type { AiDraft, ModuleInfo } from '@/api/types'
import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const modules = ref<ModuleInfo[]>([])
const drafts = ref<AiDraft[]>([])
const generating = ref(false)

const form = reactive({ module_id: '', requirement: '', count: 5, priority: 'P1' })

async function load() {
  drafts.value = await aiApi.drafts()
}

onMounted(async () => {
  modules.value = await metaApi.modules()
  form.module_id = modules.value[0]?.id ?? ''
  await load()
})

async function generate() {
  if (!form.module_id || form.requirement.trim().length < 5) {
    ElMessage.warning('请选择模块并填写需求描述（至少 5 个字）')
    return
  }
  generating.value = true
  try {
    const draft = await aiApi.generate({ ...form })
    ElMessage.success(draft.fallback ? '已用规则模板生成（未配置模型 Key 时的降级路径）' : '模型生成完成')
    await load()
  } finally {
    generating.value = false
  }
}

async function accept(draft: AiDraft, indices: number[]) {
  const r = await aiApi.accept(draft.id, indices)
  ElMessage.success(`已入库 ${r.created} 条：${r.case_codes.join('、')}`)
  await load()
}

async function reject(draft: AiDraft) {
  await aiApi.reject(draft.id)
  ElMessage.success('已驳回')
  await load()
}

const moduleName = (id?: string) => modules.value.find((m) => m.id === id)?.name ?? '—'
const expanded = ref<string[]>([])
</script>

<template>
  <div class="grid grid-3-2">
    <div class="card">
      <div class="card-head">
        <h3>生成用例草稿</h3>
        <span class="sub">产出进草稿箱，人工审核后才进用例库</span>
      </div>
      <el-form label-width="76px">
        <el-form-item label="模块">
          <el-select v-model="form.module_id" style="width: 100%">
            <el-option v-for="m in modules" :key="m.id" :label="`${m.name}（${m.code}）`" :value="m.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="需求描述">
          <el-input
            v-model="form.requirement"
            type="textarea"
            :rows="5"
            placeholder="例：语音助手应支持在导航播报过程中被唤醒打断，打断后能继续原导航；弱网时需给出明确提示并可重试"
          />
        </el-form-item>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 0 12px">
          <el-form-item label="条数"><el-input-number v-model="form.count" :min="1" :max="10" /></el-form-item>
          <el-form-item label="优先级">
            <el-select v-model="form.priority">
              <el-option label="P0" value="P0" />
              <el-option label="P1" value="P1" />
              <el-option label="P2" value="P2" />
            </el-select>
          </el-form-item>
        </div>
        <el-button v-if="auth.canWrite" type="primary" :loading="generating" style="width: 100%" @click="generate">
          生成草稿
        </el-button>
        <div class="muted" style="font-size: 12px; margin-top: 10px; line-height: 1.7">
          未配置 <span class="mono">AI_API_KEY</span> 时自动降级为规则模板（覆盖主流程 / 边界 / 中断恢复 / 空态 / 多语言主题），
          保证断网也能完整演示流程。
        </div>
      </el-form>
    </div>

    <div class="card">
      <div class="card-head">
        <h3>草稿箱</h3>
        <span class="sub">{{ drafts.length }} 份</span>
      </div>
      <div v-if="!drafts.length" class="empty">还没有草稿</div>
      <el-collapse v-model="expanded">
        <el-collapse-item v-for="d in drafts" :key="d.id" :name="d.id">
          <template #title>
            <div style="display: flex; align-items: center; gap: 8px; width: 100%">
              <span class="pill" :class="d.status === 'accepted' ? 'pill-pass' : d.status === 'rejected' ? 'pill-skip' : 'pill-p2'">
                {{ d.status === 'accepted' ? '已采纳' : d.status === 'rejected' ? '已驳回' : '待审核' }}
              </span>
              <span class="muted" style="font-size: 12px">{{ moduleName(d.module_id) }}</span>
              <span v-if="d.fallback" class="pill pill-auto">模板降级</span>
              <span style="flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; font-size: 13px">
                {{ d.requirement }}
              </span>
            </div>
          </template>

          <div v-for="(c, i) in d.cases" :key="i" style="border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; margin-bottom: 8px">
            <div style="display: flex; align-items: center; gap: 8px">
              <span class="pill" :class="`pill-${(c.priority ?? 'P2').toLowerCase()}`">{{ c.priority }}</span>
              <span style="font-size: 13px; flex: 1">{{ c.title }}</span>
            </div>
            <div class="muted" style="font-size: 12px; margin-top: 6px">前置：{{ c.precondition || '—' }}</div>
            <ol style="margin: 6px 0 0; padding-left: 18px; font-size: 12.5px; color: #46506a">
              <li v-for="s in c.steps" :key="s.no">
                {{ s.action }} <span class="muted">→ {{ s.expected }}</span>
              </li>
            </ol>
          </div>

          <div v-if="auth.canWrite && d.status === 'pending'" style="display: flex; gap: 8px; margin-top: 6px">
            <el-button size="small" type="primary" @click="accept(d, [])">全部采纳</el-button>
            <el-button size="small" @click="accept(d, [0])">只采纳第 1 条</el-button>
            <el-button size="small" @click="reject(d)">驳回</el-button>
          </div>
          <div v-else-if="d.status === 'accepted'" class="ok" style="font-size: 12px">
            已入库 {{ d.accepted_count }} 条
          </div>
        </el-collapse-item>
      </el-collapse>
    </div>
  </div>
</template>
