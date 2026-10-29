<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import { useAuthStore } from '@/stores/auth'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

const form = ref({ email: 'admin@ivi-test.com', password: 'Admin@12345' })

const demoAccounts = [
  { label: '管理员', email: 'admin@ivi-test.com', password: 'Admin@12345', desc: '全权限' },
  { label: '测试负责人', email: 'lead@ivi-test.com', password: 'Lead@12345', desc: '建用例/计划' },
  { label: '执行测试员', email: 'qa@ivi-test.com', password: 'Qa@12345', desc: '只能录入结果' },
  { label: '只读访客', email: 'viewer@ivi-test.com', password: 'Viewer@12345', desc: '演示用' },
]

function fill(email: string, password: string) {
  form.value = { email, password }
}

async function submit() {
  await auth.login(form.value.email, form.value.password)
  const redirect = (route.query.redirect as string) || '/'
  router.push(redirect)
}
</script>

<template>
  <div class="login-page">
    <section class="login-brand">
      <div>
        <div class="brand" style="padding: 0 0 40px">
          <div class="brand-mark">IV</div>
          <div class="brand-text">
            <strong>车机测试数据平台</strong>
            <span>IVI TEST PLATFORM</span>
          </div>
        </div>
        <h2>把散在 Excel 里的<br />车机测试数据，变成可追溯的资产</h2>
        <p>
          面向智能座舱与仪表的测试数据平台：用例库、测试计划、手工与自动化执行记录统一入库，
          失败按根因聚类，版本回归一键 diff，稳定性压测按 MTBF 口径出结论。
        </p>
        <ul>
          <li>用例 / 计划 / 执行全链路可追溯，失败定位到固件与设备</li>
          <li>失败日志归一化后自动聚类，同一根因不再重复分析</li>
          <li>两个批次 diff 出「新增失败 / 已修复 / 仍未修复」</li>
          <li>Appium 脚本通过静态令牌回传，手工与自动化同一张表</li>
        </ul>
      </div>
      <div style="font-size: 12px; color: #6f7f9e">Demo environment · 数据为演示用途</div>
    </section>

    <section class="login-form-wrap">
      <div class="login-form">
        <h3>登录</h3>
        <div class="hint">使用下方任一演示账号可直接进入，不同角色权限不同</div>

        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="邮箱">
            <el-input v-model="form.email" placeholder="name@company.com" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password @keyup.enter="submit" />
          </el-form-item>
          <el-button type="primary" style="width: 100%" :loading="auth.loading" @click="submit">登 录</el-button>
        </el-form>

        <div class="demo-accounts">
          <div class="title">演示账号（点击填充）</div>
          <div style="display: flex; flex-wrap: wrap; gap: 8px">
            <el-tag
              v-for="acc in demoAccounts"
              :key="acc.email"
              size="small"
              effect="plain"
              style="cursor: pointer"
              @click="fill(acc.email, acc.password)"
            >
              {{ acc.label }} · {{ acc.desc }}
            </el-tag>
          </div>
        </div>
      </div>
    </section>
  </div>
</template>
