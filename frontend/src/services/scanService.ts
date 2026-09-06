/**
 * PackSure AI — Frontend API Service Layer.
 *
 * Implements typed API service functions for:
 * 1. createScan (POST /api/v1/scans)
 * 2. getScan (GET /api/v1/scans/{id})
 * 3. reviewScan (PATCH /api/v1/scans/{id}/review)
 * 4. getHistory (GET /api/v1/history)
 * 5. getAnalytics (GET /api/v1/analytics)
 * 6. getRules (GET /api/v1/rules)
 */

import api from './api'
import type {
  AnalyticsPeriod,
  AnalyticsResponse,
  HistoryQueryParams,
  RulesQueryParams,
  RulesResponse,
  ScanCreateParams,
  ScanHistoryResponse,
  ScanInitResponse,
  ScanResponse,
  ScanReviewRequest,
} from '../types'

/**
 * Upload package image and initiate asynchronous compliance inspection.
 *
 * Calls: POST /api/v1/scans (multipart/form-data)
 */
export async function createScan(params: ScanCreateParams): Promise<ScanInitResponse> {
  const formData = new FormData()
  formData.append('image', params.image)

  if (params.product_category && params.product_category.trim() !== '') {
    formData.append('product_category', params.product_category.trim())
  }

  if (params.user_id && params.user_id.trim() !== '') {
    formData.append('user_id', params.user_id.trim())
  }

  const response = await api.post<ScanInitResponse>('/scans', formData, {
    headers: {
      'Content-Type': 'multipart/form-data',
    },
  })

  return response.data
}

/**
 * Retrieve current scan status and full compliance inspection results.
 *
 * Calls: GET /api/v1/scans/{id}
 */
export async function getScan(scanId: string): Promise<ScanResponse> {
  const cleanId = encodeURIComponent(scanId.trim())
  const response = await api.get<ScanResponse>(`/scans/${cleanId}`)
  return response.data
}

/**
 * Submit manual human reviewer resolution and audit notes for a NEEDS_REVIEW scan.
 *
 * Calls: PATCH /api/v1/scans/{id}/review
 */
export async function reviewScan(
  scanId: string,
  reviewReq: ScanReviewRequest
): Promise<ScanResponse> {
  const cleanId = encodeURIComponent(scanId.trim())
  const response = await api.patch<ScanResponse>(`/scans/${cleanId}/review`, reviewReq)
  return response.data
}

/**
 * Query paginated historical scans with optional filters.
 *
 * Calls: GET /api/v1/history
 */
export async function getHistory(
  params?: HistoryQueryParams
): Promise<ScanHistoryResponse> {
  const response = await api.get<ScanHistoryResponse>('/history', {
    params,
  })
  return response.data
}

/**
 * Retrieve aggregated compliance metrics, pass rates, and daily trends.
 *
 * Calls: GET /api/v1/analytics
 */
export async function getAnalytics(
  period: AnalyticsPeriod = '7d'
): Promise<AnalyticsResponse> {
  const response = await api.get<AnalyticsResponse>('/analytics', {
    params: { period },
  })
  return response.data
}

/**
 * Retrieve active codified Legal Metrology rules applicable to product packaging.
 *
 * Calls: GET /api/v1/rules
 */
export async function getRules(
  params?: RulesQueryParams
): Promise<RulesResponse> {
  const response = await api.get<RulesResponse>('/rules', {
    params,
  })
  return response.data
}
