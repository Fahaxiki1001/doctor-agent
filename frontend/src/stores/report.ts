import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ReportMeasurement, ReportResponse } from '../types'
import {
  analyzeReport,
  cancelReport,
  confirmReportMeasurements,
  deleteReport,
  getReport,
  listReports,
  retryReport,
  uploadReport,
} from '../api/report'

export const useReportStore = defineStore('reports', () => {
  const reports = ref<ReportResponse[]>([])
  const current = ref<ReportResponse | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  function messageFrom(errorValue: unknown) {
    return (
      (errorValue as { response?: { data?: { detail?: string } } }).response?.data?.detail ||
      (errorValue instanceof Error ? errorValue.message : '报告操作失败')
    )
  }

  async function loadList() {
    loading.value = true
    error.value = null
    try {
      reports.value = await listReports()
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  async function load(reportId: string) {
    loading.value = true
    error.value = null
    try {
      current.value = await getReport(reportId)
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  async function upload(file: File, type: 'lab_report' | 'physical_exam' | 'other') {
    loading.value = true
    error.value = null
    try {
      current.value = await uploadReport(file, type)
      current.value = await analyzeReport(current.value.report_id)
      return current.value
    } catch (err) {
      error.value = messageFrom(err)
      return null
    } finally {
      loading.value = false
    }
  }

  async function confirm(measurements: ReportMeasurement[]) {
    if (!current.value) return
    loading.value = true
    error.value = null
    try {
      current.value = await confirmReportMeasurements(current.value.report_id, measurements)
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  async function retry() {
    if (!current.value) return
    loading.value = true
    error.value = null
    try {
      current.value = await retryReport(current.value.report_id)
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  async function remove(reportId: string) {
    await deleteReport(reportId)
    reports.value = reports.value.filter((item) => item.report_id !== reportId)
    if (current.value?.report_id === reportId) current.value = null
  }

  async function cancel() {
    if (!current.value) return
    loading.value = true
    error.value = null
    try {
      current.value = await cancelReport(current.value.report_id)
    } catch (err) {
      error.value = messageFrom(err)
    } finally {
      loading.value = false
    }
  }

  return {
    reports,
    current,
    loading,
    error,
    loadList,
    load,
    upload,
    confirm,
    retry,
    remove,
    cancel,
  }
})
