<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()
const username = ref('')

function defaultHome(): string {
  return auth.canAccessOPortal ? '/o/dashboard' : '/chat'
}

async function handleLogin() {
  if (!username.value.trim()) return
  try {
    await auth.login(username.value)
    const redirect = typeof route.query.redirect === 'string' ? route.query.redirect : ''
    const target = redirect && redirect !== '/login' ? redirect : defaultHome()
    await router.replace(target)
  } catch {
    // 错误信息由认证 Store 展示
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-slate-50 px-4">
    <section class="w-full max-w-md bg-white border border-slate-200 rounded-2xl p-8 shadow-sm">
      <div class="text-center mb-6">
        <div
          class="w-12 h-12 mx-auto mb-3 rounded-xl bg-blue-500 text-white flex items-center justify-center font-bold"
        >
          M
        </div>
        <h1 class="text-xl font-semibold text-slate-800">登录 MediZJ</h1>
        <p class="mt-2 text-sm text-slate-500">输入用户名即可登录，首次使用会自动创建账号</p>
      </div>
      <form class="space-y-4" @submit.prevent="handleLogin">
        <input
          v-model="username"
          autocomplete="username"
          autofocus
          maxlength="64"
          pattern="[A-Za-z0-9_-]+"
          placeholder="用户名"
          class="w-full px-3 py-2.5 border border-slate-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        />
        <div v-if="auth.error" class="text-sm text-red-600">{{ auth.error }}</div>
        <button
          type="submit"
          :disabled="auth.loading || !username.trim()"
          class="w-full py-2.5 bg-blue-600 text-white text-sm rounded-lg hover:bg-blue-700 disabled:bg-slate-300 transition"
        >
          {{ auth.loading ? '登录中...' : '登录' }}
        </button>
      </form>
      <p class="mt-5 text-xs leading-relaxed text-amber-600 bg-amber-50 rounded-lg p-3">
        当前为免密登录，仅适用于本地或可信网络环境，请勿用于公开生产环境。
      </p>
    </section>
  </div>
</template>
