import { useState, useEffect } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import { Mail, Lock, AlertCircle } from 'lucide-react'

export default function Login() {
const [email, setEmail] = useState('')
const [password, setPassword] = useState('')
const [errors, setErrors] = useState({})
const [loading, setLoading] = useState(false)
const [loggedIn, setLoggedIn] = useState(false)

const { user, login } = useAuth()
const { success, error: showError } = useToast()
const navigate = useNavigate()

useEffect(() => {
  if (user && loggedIn) {
    navigate('/dashboard')
  }
}, [user, loggedIn, navigate])

  const validate = () => {
    const newErrors = {}
    
    if (!email) {
      newErrors.email = 'Email обязателен'
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      newErrors.email = 'Некорректный формат email'
    }
    
    if (!password) {
      newErrors.password = 'Пароль обязателен'
    }
    
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

const handleSubmit = async (e) => {
  e.preventDefault()
  
  if (!validate()) return
  
  setLoading(true)

  try {
    await login(email, password)
    console.log('Token in localStorage:', localStorage.getItem('access_token')?.substring(0, 20) + '...')
    success('Успешный вход в систему')
    setLoggedIn(true)
  } catch (err) {
    showError(err.response?.data?.error || 'Произошла ошибка при входе')
  } finally {
    setLoading(false)
  }
}

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white">Вход в систему</h2>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Или <Link to="/register" className="text-primary-600 hover:text-primary-500 dark:text-primary-400 font-medium">зарегистрируйтесь</Link>
          </p>
        </div>

        <form className="card space-y-6" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Email
            </label>
            <div className="flex items-center border border-gray-300 rounded-lg px-3 bg-white dark:bg-gray-800 dark:border-gray-600 focus-within:ring-2 focus-within:ring-primary-500 focus-within:border-transparent transition-all">
              <Mail className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => {
                  setEmail(e.target.value)
                  if (errors.email) setErrors({ ...errors, email: '' })
                }}
                className={`flex-1 px-3 py-2.5 bg-transparent outline-none text-gray-900 dark:text-gray-100 dark:bg-transparent ${errors.email ? 'border-red-500' : ''}`}
                placeholder="example@mail.ru"
              />
            </div>
            {errors.email && (
              <p className="mt-1 text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {errors.email}
              </p>
            )}
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Пароль
            </label>
            <div className="flex items-center border border-gray-300 rounded-lg px-3 bg-white dark:bg-gray-800 dark:border-gray-600 focus-within:ring-2 focus-within:ring-primary-500 focus-within:border-transparent transition-all">
              <Lock className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
              <input
                id="password"
                type="password"
                value={password}
                onChange={(e) => {
                  setPassword(e.target.value)
                  if (errors.password) setErrors({ ...errors, password: '' })
                }}
                className={`flex-1 px-3 py-2.5 bg-transparent outline-none text-gray-900 dark:text-gray-100 dark:bg-transparent ${errors.password ? 'border-red-500' : ''}`}
                placeholder="••••••••"
              />
            </div>
            {errors.password && (
              <p className="mt-1 text-sm text-red-600 flex items-center gap-1">
                <AlertCircle className="h-3 w-3" />
                {errors.password}
              </p>
            )}
          </div>

          <div className="flex items-center justify-between">
            <div className="text-sm">
              <Link to="/forgot-password" className="text-primary-600 hover:text-primary-500 dark:text-primary-400">
                Забыли пароль?
              </Link>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full flex items-center justify-center"
          >
            {loading ? (
              <span className="flex items-center gap-2">
                <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></span>
                Вход...
              </span>
            ) : 'Войти'}
          </button>
        </form>
      </div>
    </div>
  )
}
