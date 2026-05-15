import { useState } from 'react'
import { Link } from 'react-router-dom'
import api from '../utils/api'
import { Mail, AlertCircle, CheckCircle } from 'lucide-react'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [error, setError] = useState('')
  const [success, setSuccess] = useState(false)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await api.post('/auth/forgot-password', { email })
      setSuccess(true)
    } catch (err) {
      setError(err.response?.data?.error || 'Произошла ошибка')
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full text-center">
          <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto mb-4">
            <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
          </div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">Письмо отправлено</h2>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Если email существует в системе, на него отправлены инструкции по восстановлению пароля.
          </p>
          <Link to="/login" className="btn-primary inline-block">
            Вернуться ко входу
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white">Восстановление пароля</h2>
          <p className="mt-2 text-gray-600 dark:text-gray-400">
            Введите email, и мы отправим инструкции
          </p>
        </div>

        <form className="card space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="flex items-center space-x-2 p-3 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-lg">
              <AlertCircle className="h-5 w-5" />
              <span>{error}</span>
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              Email
            </label>
            <div className="flex items-center border border-gray-300 rounded-lg px-3 bg-white dark:bg-gray-800 dark:border-gray-600 focus-within:ring-2 focus-within:ring-primary-500 focus-within:border-transparent transition-all">
              <Mail className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0 mr-2" />
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex-1 px-3 py-2.5 bg-transparent outline-none text-gray-900 dark:text-gray-100 dark:bg-transparent"
                placeholder="example@mail.ru"
                required
              />
            </div>
          </div>

          <button type="submit" disabled={loading} className="btn-primary w-full">
            {loading ? 'Отправка...' : 'Восстановить пароль'}
          </button>

          <div className="text-center">
            <Link to="/login" className="text-sm text-primary-600 dark:text-primary-400 hover:text-primary-500 dark:hover:text-primary-300">
              Вернуться ко входу
            </Link>
          </div>
        </form>
      </div>
    </div>
  )
}
