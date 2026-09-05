// TODO: Implement API client in Phase 1 (Frontend Dev)
// Base axios instance and interceptors will go here.

import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json',
  },
})

export default api
