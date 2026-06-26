import { useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useToast } from '../context/ToastContext'
import api from '../utils/api'
import { Lock, CheckCircle } from 'lucide-react'

export default function ResetPassword() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const navigate = useNavigate()
  const { success, error: showError } = useToast()

  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [loading, setLoading] = useState(false)
  const [done, setDone] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!token) {
      showError('Ссылка недействительна')
      return
    }
    if (password.length < 6) {
      showError('Пароль должен быть не менее 6 символов')
      return
    }
    if (password !== confirm) {
      showError('Пароли не совпадают')
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/reset-password', { token, new_password: password })
      setDone(true)
      success('Пароль изменён')
      setTimeout(() => navigate('/login'), 1500)
    } catch (err) {
      showError(err.response?.data?.error || 'Не удалось сбросить пароль')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white">Новый пароль</h2>
        </div>

        {done ? (
          <div className="card text-center space-y-4">
            <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
            </div>
            <p className="text-gray-700 dark:text-gray-300">Пароль изменён. Перенаправляем ко входу...</p>
          </div>
        ) : (
          <form className="card space-y-6" onSubmit={handleSubmit}>
            {!token && (
              <p className="text-sm text-red-600 dark:text-red-400">
                Ссылка недействительна или истекла. Запросите сброс заново на странице «Забыли пароль».
              </p>
            )}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Новый пароль
              </label>
              <div className="flex items-center border border-gray-300 rounded-lg px-3 bg-white dark:bg-gray-800 dark:border-gray-600 focus-within:ring-2 focus-within:ring-primary-500 transition-all">
                <Lock className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="flex-1 px-3 py-2.5 bg-transparent outline-none text-gray-900 dark:text-gray-100"
                  placeholder="••••••••"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Повторите пароль
              </label>
              <div className="flex items-center border border-gray-300 rounded-lg px-3 bg-white dark:bg-gray-800 dark:border-gray-600 focus-within:ring-2 focus-within:ring-primary-500 transition-all">
                <Lock className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
                <input
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="flex-1 px-3 py-2.5 bg-transparent outline-none text-gray-900 dark:text-gray-100"
                  placeholder="••••••••"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading || !token}
              className="btn-navy w-full flex items-center justify-center"
            >
              {loading ? 'Сохраняем...' : 'Сохранить пароль'}
            </button>
            <div className="text-center text-sm">
              <Link to="/login" className="text-primary-600 dark:text-primary-400 hover:underline">
                Ко входу
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
