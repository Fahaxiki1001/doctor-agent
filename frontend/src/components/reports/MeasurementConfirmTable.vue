<script setup lang="ts">
import { ref } from 'vue'
import type { ReportMeasurement } from '../../types'

const props = defineProps<{ measurements: ReportMeasurement[]; loading?: boolean }>()
const emit = defineEmits<{ confirm: [measurements: ReportMeasurement[]] }>()
const rows = ref<ReportMeasurement[]>(props.measurements.map((item) => ({ ...item })))

function markUnable(row: ReportMeasurement) {
  row.unable_to_confirm = !row.unable_to_confirm
  if (row.unable_to_confirm) row.user_confirmed = false
}

function markConfirmed(row: ReportMeasurement) {
  row.user_confirmed = !row.user_confirmed
  if (row.user_confirmed) row.unable_to_confirm = false
}
</script>

<template>
  <section>
    <div class="mb-4">
      <h2 class="text-base font-semibold text-slate-900">确认识别结果</h2>
      <p class="mt-1 text-sm text-slate-500">
        请对照原报告修改并逐项确认。未确认的指标不会用于解释。
      </p>
    </div>
    <div class="hidden overflow-x-auto border border-slate-200 bg-white md:block">
      <table class="w-full min-w-[900px] text-left text-sm">
        <thead class="bg-slate-50 text-xs text-slate-600">
          <tr>
            <th class="p-3">项目</th>
            <th class="p-3">数值</th>
            <th class="p-3">单位</th>
            <th class="p-3">参考范围</th>
            <th class="p-3">置信度</th>
            <th class="p-3">处理</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200">
          <tr
            v-for="row in rows"
            :key="row.measurement_id"
            :class="row.deleted ? 'opacity-40' : ''"
          >
            <td class="p-2">
              <input
                v-model="row.name"
                :disabled="row.deleted"
                :aria-label="`${row.name || '指标'}项目名称`"
                class="w-36 rounded border border-slate-300 px-2 py-1.5"
              />
            </td>
            <td class="p-2">
              <input
                v-model="row.value"
                :disabled="row.deleted"
                :aria-label="`${row.name || '指标'}数值`"
                class="w-24 rounded border border-slate-300 px-2 py-1.5"
              />
            </td>
            <td class="p-2">
              <input
                v-model="row.unit"
                :disabled="row.deleted"
                :aria-label="`${row.name || '指标'}单位`"
                class="w-24 rounded border border-slate-300 px-2 py-1.5"
              />
            </td>
            <td class="p-2">
              <input
                v-model="row.reference_range"
                :disabled="row.deleted"
                :aria-label="`${row.name || '指标'}参考范围`"
                class="w-32 rounded border border-slate-300 px-2 py-1.5"
              />
            </td>
            <td class="p-3 tabular-figures">{{ Math.round(row.confidence * 100) }}%</td>
            <td class="p-2">
              <div class="flex items-center gap-3 whitespace-nowrap">
                <label
                  ><input
                    type="checkbox"
                    :checked="row.user_confirmed"
                    :disabled="row.deleted"
                    @change="markConfirmed(row)"
                  />
                  确认</label
                >
                <label
                  ><input
                    type="checkbox"
                    :checked="row.unable_to_confirm"
                    :disabled="row.deleted"
                    @change="markUnable(row)"
                  />
                  无法确认</label
                >
                <button class="text-red-700" type="button" @click="row.deleted = !row.deleted">
                  {{ row.deleted ? '恢复' : '删除' }}
                </button>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>
    <div class="space-y-3 md:hidden">
      <fieldset
        v-for="row in rows"
        :key="row.measurement_id"
        class="border border-slate-200 bg-white p-4"
        :class="row.deleted ? 'opacity-50' : ''"
      >
        <legend
          class="flex w-full items-center justify-between gap-3 px-1 text-sm font-medium text-slate-800"
        >
          <span class="truncate">{{ row.name || '未命名指标' }}</span>
          <span class="shrink-0 text-xs font-normal text-slate-500"
            >置信度 {{ Math.round(row.confidence * 100) }}%</span
          >
        </legend>
        <div class="mt-3 grid grid-cols-2 gap-3">
          <label class="col-span-2 text-xs text-slate-600">
            项目
            <input
              v-model="row.name"
              :disabled="row.deleted"
              class="mt-1 h-10 w-full rounded border border-slate-300 px-3 text-sm"
            />
          </label>
          <label class="text-xs text-slate-600">
            数值
            <input
              v-model="row.value"
              :disabled="row.deleted"
              class="mt-1 h-10 w-full min-w-0 rounded border border-slate-300 px-3 text-sm"
            />
          </label>
          <label class="text-xs text-slate-600">
            单位
            <input
              v-model="row.unit"
              :disabled="row.deleted"
              class="mt-1 h-10 w-full min-w-0 rounded border border-slate-300 px-3 text-sm"
            />
          </label>
          <label class="col-span-2 text-xs text-slate-600">
            参考范围
            <input
              v-model="row.reference_range"
              :disabled="row.deleted"
              class="mt-1 h-10 w-full rounded border border-slate-300 px-3 text-sm"
            />
          </label>
        </div>
        <div class="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-700">
          <label class="flex items-center gap-2"
            ><input
              type="checkbox"
              :checked="row.user_confirmed"
              :disabled="row.deleted"
              @change="markConfirmed(row)"
            />
            确认</label
          >
          <label class="flex items-center gap-2"
            ><input
              type="checkbox"
              :checked="row.unable_to_confirm"
              :disabled="row.deleted"
              @change="markUnable(row)"
            />
            无法确认</label
          >
          <button class="ml-auto text-red-700" type="button" @click="row.deleted = !row.deleted">
            {{ row.deleted ? '恢复' : '删除' }}
          </button>
        </div>
      </fieldset>
    </div>
    <div class="mt-4 flex justify-end">
      <button
        type="button"
        :disabled="
          loading || !rows.some((row) => row.user_confirmed || row.unable_to_confirm || row.deleted)
        "
        class="rounded-lg bg-blue-600 px-5 py-2 text-sm font-medium text-white hover:bg-blue-700 disabled:bg-slate-300"
        @click="emit('confirm', rows)"
      >
        {{ loading ? '生成解释中...' : '确认并生成解释' }}
      </button>
    </div>
  </section>
</template>
