import axios from 'axios'

const baseURL = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL,
  headers: { 'Content-Type': 'application/json' },
  timeout: 90000, // 90s to comfortably accommodate Render free-tier cold starts
})

// Attach auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('sb_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// Auto-retry on cold-start errors (502, 503, 504, ECONNABORTED)
api.interceptors.response.use(
  (res) => res,
  async (err) => {
    const config = err.config

    // If it's a cold-start timeout or gateway error and we haven't retried yet
    const isColdStart =
      err.code === 'ECONNABORTED' ||
      err.message?.includes('timeout') ||
      err.message?.includes('Network Error') ||
      [502, 503, 504].includes(err.response?.status)

    if (isColdStart && config && !config._retry) {
      config._retry = true
      // Wait 3 seconds for Render to finish spinning up, then retry transparently
      await new Promise((resolve) => setTimeout(resolve, 3000))
      return api(config)
    }

    if (err.code === 'ECONNABORTED' || err.message?.includes('timeout')) {
      err.response = {
        ...(err.response || {}),
        data: {
          detail: 'Server was waking up from cold start. Please click once more to proceed.'
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

/**
 * Fire-and-forget pre-warm ping to wake up Render as soon as the user opens the frontend.
 */
export function prewarmBackend() {
  try {
    const healthUrl = baseURL.endsWith('/api') ? `${baseURL}/health` : `${baseURL}/api/health`
    fetch(healthUrl, { method: 'GET', mode: 'cors' }).catch(() => {
      // Ignore background errors — this is purely a wake-up signal
    })
  } catch (_) {}
}

export default api
