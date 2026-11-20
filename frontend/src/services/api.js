import axios from 'axios'

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  headers: { 'Content-Type': 'application/json' },
  timeout: 45000, // 45s to accommodate Render free-tier cold starts
})

// Attach auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sb_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-logout on 401 & friendly timeout handling
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
      err.response = {
        ...(err.response || {}),
        data: {
          detail: 'Server is waking up (Render cold start). Please wait a moment and try again.'
        }
      }
    } else if (err.response?.status === 401) {
      localStorage.removeItem('sb_token')
      localStorage.removeItem('sb_user')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
