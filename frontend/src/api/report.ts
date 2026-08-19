import api from './client'
import type { ReportMeasurement, ReportResponse } from '../types'

export async function uploadReport(
  file: File,
  documentType: 'lab_report' | 'physical_exam' | 'other' = 'other',
): Promise<ReportResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('document_type', documentType)
  const { data } = await api.post('/reports', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
  })
  return data
}

export async function listReports(): Promise<ReportResponse[]> {
  const { data } = await api.get('/reports')
  return data
}

export async function getReport(reportId: string): Promise<ReportResponse> {
  const { data } = await api.get(`/reports/${reportId}`)
  return data
}

export async function analyzeReport(reportId: string): Promise<ReportResponse> {
  const { data } = await api.post(`/reports/${reportId}/analyze`)
  return data
}

export async function confirmReportMeasurements(
  reportId: string,
  measurements: ReportMeasurement[],
): Promise<ReportResponse> {
  const { data } = await api.put(`/reports/${reportId}/measurements/confirm`, {
    measurements,
  })
  return data
}

export async function retryReport(reportId: string): Promise<ReportResponse> {
  const { data } = await api.post(`/reports/${reportId}/retry`)
  return data
}

export async function cancelReport(reportId: string): Promise<ReportResponse> {
  const { data } = await api.post(`/reports/${reportId}/cancel`)
  return data
}

export async function deleteReport(reportId: string): Promise<void> {
  await api.delete(`/reports/${reportId}`)
}
