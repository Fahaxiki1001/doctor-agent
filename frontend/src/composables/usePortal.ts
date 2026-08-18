import { computed } from 'vue'
import { useRoute } from 'vue-router'
import type { Portal } from '../api/auth'

/**
 * 当前处于哪个端只由路由决定，与账号角色无关。
 * 管理员访问 C 端路由时同样得到患者视角。
 */
export function usePortal() {
  const route = useRoute()

  const activePortal = computed<Portal>(() => (route.meta.portal as Portal) ?? 'c')
  const isOPortal = computed(() => activePortal.value === 'o')
  const isCPortal = computed(() => activePortal.value === 'c')
  const showInternalDetails = computed(() => isOPortal.value)

  return { activePortal, isOPortal, isCPortal, showInternalDetails }
}
