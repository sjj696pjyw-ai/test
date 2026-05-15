import axios from 'axios'

const api = axios.create({
  baseURL: 'http://127.0.0.1:5001/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

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
