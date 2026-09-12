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

/**
 * Resolves a storage or artifact path returned by the backend into a fully qualified or proxy-ready URL.
 *
 * - Leaves absolute URLs (http:// or https://) untouched.
 * - Converts relative paths (e.g., "storage/scans/xyz/evidence.jpg" or "/storage/...") to target backend origin.
 * - Safely normalizes Windows backslashes and handles leading/trailing slashes.
 * - Uses VITE_API_BASE_URL if configured; otherwise defaults to the backend origin.
 */
export const resolveArtifactUrl = (path?: string | null): string | null => {
  if (!path || typeof path !== 'string' || !path.trim()) {
    return null
  }

  const normalized = path.trim().replace(/\\/g, '/')
  if (normalized.startsWith('http://') || normalized.startsWith('https://')) {
    return normalized
  }

  const cleanRelative = normalized.startsWith('/') ? normalized.slice(1) : normalized
  const rawEnv = (import.meta.env.VITE_API_BASE_URL || '').trim()

  let backendOrigin = 'http://localhost:8000'
  if (rawEnv) {
    // Strip any trailing /api or /api/v1 prefix to get the root server origin
    backendOrigin = rawEnv.replace(/\/api(?:\/v1)?\/?$/, '').replace(/\/+$/, '')
  }

  return `${backendOrigin}/${cleanRelative}`
}

export default api
