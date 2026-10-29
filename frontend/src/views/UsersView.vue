<script setup lang="ts">
import { ElMessage, ElMessageBox } from 'element-plus'
import { onMounted, reactive, ref } from 'vue'

import { userApi } from '@/api'
import type { UserInfo } from '@/api/types'

const users = ref<UserInfo[]>([])
const loading = ref(false)
const dialog = ref(false)
const form = reactive({ email: '', full_name: '', password: '', role: 'executor' })

const roleOptions = [
  { value: 'admin', label: '管理员', desc: '全部权限，含用户管理' },
  { value: 'lead', label: '测试负责人', desc: '建用例、建计划、看全部报表' },
  { value: 'executor', label: '执行测试员', desc: '只能录入自己负责用例的结果' },
  { value: 'viewer', label: '只读访客', desc: '演示账号，只能看' },
]

const roleLabel = (r: string) => roleOptions.find((o) => o.value === r)?.label ?? r
const rolePill = (r: string) => ({ admin: 'pill-fail', lead: 'pill-p2', executor: 'pill-pass', viewer: 'pill-skip' })[r] ?? 'pill-skip'

async function load() {
  loading.value = true
  try {
    users.value = await userApi.list()
  } finally {
    loading.value = false
  }
}

onMounted(load)

async function create() {
  if (!form.email || !form.full_name || form.password.length < 8) {
    ElMessage.warning('邮箱、姓名必填，密码至少 8 位')
    return
  }
  await userApi.create({ ...form })
  ElMessage.success('已创建')
  dialog.value = false
  Object.assign(form, { email: '', full_name: '', password: '', role: 'executor' })
  await load()
}

async function toggle(row: UserInfo) {
  await userApi.update(row.id, { is_active: !row.is_active })
  await load()
}

async function changeRole(row: UserInfo, role: string) {
  await userApi.update(row.id, { role })
  ElMessage.success('角色已更新')
  await load()
}

async function remove(row: UserInfo) {
  await ElMessageBox.confirm(`确认删除 ${row.full_name}？`, '删除用户', { type: 'warning' })
  await userApi.remove(row.id)
  ElMessage.success('已删除')
  await load()
}
</script>

<template>
  <div>
    <div class="toolbar">
      <span class="muted" style="font-size: 12.5px">四种角色对应四套能力边界，后端按依赖注入逐接口校验，前端只做展示层的按钮隐藏</span>
      <div class="spacer" />
      <el-button size="small" @click="load">刷新</el-button>
      <el-button type="primary" size="small" @click="dialog = true">新建用户</el-button>
    </div>

    <div class="card" style="padding: 0">
      <el-table v-loading="loading" :data="users" size="small">
        <el-table-column prop="full_name" label="姓名" width="140" />
        <el-table-column prop="email" label="邮箱" min-width="220">
          <template #default="{ row }"><span class="mono">{{ row.email }}</span></template>
        </el-table-column>
        <el-table-column label="角色" width="200">
          <template #default="{ row }">
            <el-select :model-value="row.role" size="small" style="width: 130px" @change="(v: string) => changeRole(row, v)">
              <el-option v-for="o in roleOptions" :key="o.value" :label="o.label" :value="o.value" />
            </el-select>
          </template>
        </el-table-column>
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <span class="pill" :class="row.is_active ? 'pill-pass' : 'pill-skip'">{{ row.is_active ? '启用' : '停用' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="创建时间" width="180">
          <template #default="{ row }">{{ new Date(row.created_at).toLocaleString('zh-CN', { hour12: false }) }}</template>
        </el-table-column>
        <el-table-column label="操作" width="150" fixed="right">
          <template #default="{ row }">
            <el-button text size="small" @click="toggle(row)">{{ row.is_active ? '停用' : '启用' }}</el-button>
            <el-button text size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="card" style="margin-top: 16px">
      <div class="card-head"><h3>角色能力对照</h3></div>
      <el-table :data="roleOptions" size="small">
        <el-table-column label="角色" width="160">
          <template #default="{ row }">
            <span class="pill" :class="rolePill(row.value)">{{ row.label }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="desc" label="说明" />
      </el-table>
    </div>

    <el-dialog v-model="dialog" title="新建用户" width="480px">
      <el-form label-width="72px">
        <el-form-item label="姓名" required><el-input v-model="form.full_name" /></el-form-item>
        <el-form-item label="邮箱" required><el-input v-model="form.email" placeholder="name@company.com" /></el-form-item>
        <el-form-item label="密码" required><el-input v-model="form.password" type="password" show-password placeholder="至少 8 位" /></el-form-item>
        <el-form-item label="角色">
          <el-select v-model="form.role" style="width: 100%">
            <el-option v-for="o in roleOptions" :key="o.value" :label="`${o.label} · ${o.desc}`" :value="o.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialog = false">取消</el-button>
        <el-button type="primary" @click="create">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>
