import { describe, expect, it } from 'vitest'
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { createRouter, createWebHistory } from 'vue-router'
import { usePortal } from '../usePortal'

const Probe = defineComponent({
  setup() {
    const portal = usePortal()
    return () =>
      h('div', [
        h('span', { class: 'active' }, portal.activePortal.value),
        h('span', { class: 'internal' }, String(portal.showInternalDetails.value)),
      ])
  },
})

function createTestRouter() {
  return createRouter({
    history: createWebHistory(),
    routes: [
      { path: '/chat', name: 'Chat', meta: { portal: 'c' }, component: Probe },
      { path: '/o/dashboard', name: 'Dashboard', meta: { portal: 'o' }, component: Probe },
      { path: '/unknown', name: 'Unknown', component: Probe },
    ],
  })
}

async function mountAt(path: string) {
  const router = createTestRouter()
  await router.push(path)
  await router.isReady()
  return mount(Probe, { global: { plugins: [router] } })
}

describe('usePortal', () => {
  it('C 端路由不暴露内部详情', async () => {
    const wrapper = await mountAt('/chat')

    expect(wrapper.find('.active').text()).toBe('c')
    expect(wrapper.find('.internal').text()).toBe('false')
  })

  it('O 端路由展示内部详情', async () => {
    const wrapper = await mountAt('/o/dashboard')

    expect(wrapper.find('.active').text()).toBe('o')
    expect(wrapper.find('.internal').text()).toBe('true')
  })

  it('未标记端类型的路由回落到 C 端', async () => {
    const wrapper = await mountAt('/unknown')

    expect(wrapper.find('.active').text()).toBe('c')
    expect(wrapper.find('.internal').text()).toBe('false')
  })
})
