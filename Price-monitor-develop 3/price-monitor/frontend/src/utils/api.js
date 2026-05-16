import axios from 'axios'
import { fixEncodingRecursive } from './encoding'

const api = axios.create({
  baseURL: 'http://127.0.0.1:5001/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

// Интерцептор для автоматического исправления кодировки в ответах
api.interceptors.response.use(
  (response) => {
    // Применяем исправление кодировки ко всем данным ответа
    if (response.data) {
      response.data = fixEncodingRecursive(response.data)
    }
    return response
  },
  (error) => Promise.reject(error)
)

api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      const isAuthCheck = error.config.url?.includes('/auth/me')
      if (!isAuthCheck) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
      }
    }
    return Promise.reject(error)
  }
)

export default api
