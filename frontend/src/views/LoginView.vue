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
  <div
    class="min-h-screen flex items-center justify-center bg-gradient-to-br from-blue-50/70 via-slate-50 to-teal-50/50 px-4"
  >
    <section class="surface-card w-full max-w-md rounded-2xl border p-8 shadow-design-lg">
      <div class="text-center mb-6">
        <div
          class="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-blue-600 to-blue-500 font-bold text-white shadow-design-sm"
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
          class="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
        />
        <div v-if="auth.error" class="text-sm text-red-600">{{ auth.error }}</div>
        <button
          type="submit"
          :disabled="auth.loading || !username.trim()"
          class="w-full rounded-lg bg-gradient-to-r from-blue-600 to-blue-500 py-2.5 text-sm text-white shadow-design-sm hover:from-blue-700 hover:to-blue-600 disabled:from-slate-300 disabled:to-slate-300 disabled:shadow-none transition-all"
        >
          {{ auth.loading ? '登录中...' : '登录' }}
        </button>
      </form>
      <p
        class="mt-5 rounded-lg border-l-2 border-slate-300 bg-slate-50 px-3 py-2.5 text-xs leading-relaxed text-slate-600"
      >
        当前为免密登录，仅适用于本地或可信网络环境，请勿用于公开生产环境。
      </p>
    </section>
  </div>
</template>
