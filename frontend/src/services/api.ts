/**
 * PackSure AI — Core Axios HTTP Client Configuration.
 *
 * Configures the base HTTP client for /api/v1 communication,
 * preserving Vite proxy capabilities and structured error propagation.
 */

import axios, { AxiosError } from 'axios'

/** Structured interface for normalized backend error responses. */
export interface ApiErrorDetail {
  status: number
  message: string
  details?: unknown
}

// Resolve base URL: if VITE_API_BASE_URL is defined, ensure /api/v1 prefix; otherwise default to '/api/v1' for Vite proxy
const rawBaseUrl = import.meta.env.VITE_API_BASE_URL || ''
const apiBaseUrl = rawBaseUrl
  ? rawBaseUrl.endsWith('/api/v1')
    ? rawBaseUrl
    : `${rawBaseUrl.replace(/\/+$/, '')}/api/v1`
  : '/api/v1'

export const api = axios.create({
  baseURL: apiBaseUrl,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Centralized error interceptor ensuring HTTP status codes and detail messages are preserved
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string | unknown; message?: string }>) => {
    if (error.response) {
      const errorData = error.response.data
      const detailMsg =
        typeof errorData?.detail === 'string'
          ? errorData.detail
          : errorData?.message || error.message || 'API request failed'

      const apiError: ApiErrorDetail = {
        status: error.response.status,
        message: detailMsg,
        details: errorData?.detail,
      }
      return Promise.reject(apiError)
    }

    const networkError: ApiErrorDetail = {
      status: 0,
      message: error.message || 'Network error: could not connect to PackSure API backend',
    }
    return Promise.reject(networkError)
  }
)

export default api
