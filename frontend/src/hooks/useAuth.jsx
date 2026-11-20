import React, { createContext, useContext, useState, useEffect, useCallback } from 'react'
import api from '../services/api.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem('sb_token'))
  const [user, setUser]   = useState(() => {
    try { return JSON.parse(localStorage.getItem('sb_user')) } catch { return null }
  })
  const [loading, setLoading] = useState(true)

  const logout = useCallback(() => {
    localStorage.removeItem('sb_token')
    localStorage.removeItem('sb_user')
    setToken(null)
    setUser(null)
  }, [])

  // Verify and refresh current user profile on app load
  useEffect(() => {
    const refreshProfile = async () => {
      const storedToken = localStorage.getItem('sb_token')
      if (!storedToken) {
        setLoading(false)
        return
      }

      try {
        const { data } = await api.get('/auth/me')
        setUser(prev => ({
          ...prev,
          ...data,
          business_name: data.business_name || prev?.business_name,
          business_slug: data.business_slug || prev?.business_slug,
          widget_token: data.widget_token || prev?.widget_token,
        }))
        localStorage.setItem('sb_user', JSON.stringify({
          ...JSON.parse(localStorage.getItem('sb_user') || '{}'),
          ...data
        }))
      } catch (err) {
        if (err.response?.status === 401 || err.response?.status === 403) {
          logout()
        }
      } finally {
        setLoading(false)
      }
    }

    refreshProfile()
  }, [logout])

  const login = async (email, password) => {
    const { data } = await api.post('/auth/login', { email, password })
    localStorage.setItem('sb_token', data.access_token)
    localStorage.setItem('sb_user', JSON.stringify(data))
    setToken(data.access_token)
    setUser(data)

    // Non-blocking background profile enrichment
    api.get('/auth/me', {
      headers: { Authorization: `Bearer ${data.access_token}` }
    }).then(meRes => {
      const fullUser = { ...data, ...meRes.data }
      setUser(fullUser)
      localStorage.setItem('sb_user', JSON.stringify(fullUser))
    }).catch(() => {})

    return data
  }

  const register = async (payload) => {
    const { data } = await api.post('/auth/register', payload)
    localStorage.setItem('sb_token', data.access_token)
    localStorage.setItem('sb_user', JSON.stringify(data))
    setToken(data.access_token)
    setUser(data)

    try {
      const meRes = await api.get('/auth/me', {
        headers: { Authorization: `Bearer ${data.access_token}` }
      })
      const fullUser = { ...data, ...meRes.data }
      setUser(fullUser)
      localStorage.setItem('sb_user', JSON.stringify(fullUser))
    } catch {
      // Keep basic data
    }

    return data
  }

  return (
    <AuthContext.Provider value={{ token, user, login, register, logout, loading }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
