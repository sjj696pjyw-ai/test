import { createContext, useContext, useState, useEffect } from 'react'
import api from '../utils/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const token = localStorage.getItem('access_token')
    if (token) {
      fetchUser()
    } else {
      setLoading(false)
    }
  }, [])

  const fetchUser = async () => {
    try {
      const response = await api.get('/auth/me')
      setUser(response.data.user)
    } catch (error) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
    } finally {
      setLoading(false)
    }
  }

  const setSession = (data) => {
    localStorage.setItem('access_token', data.access_token)
    localStorage.setItem('refresh_token', data.refresh_token)
    setUser(data.user)
  }

  const login = async (email, password) => {
    const response = await api.post('/auth/login', { email, password })
    setSession(response.data)
    return response.data
  }

  // Регистрация больше не логинит сразу — нужно подтвердить email.
  const register = async (email, password) => {
    const response = await api.post('/auth/register', { email, password, consent: true })
    return response.data
  }

  // Подтверждение email по токену из письма — логинит при успехе.
  const confirmEmail = async (token) => {
    const response = await api.post('/auth/confirm-email', { token })
    setSession(response.data)
    return response.data
  }

  const logout = () => {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, confirmEmail, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export const useAuth = () => {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}
