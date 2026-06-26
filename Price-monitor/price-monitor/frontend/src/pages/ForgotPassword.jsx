import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useToast } from '../context/ToastContext'
import api from '../utils/api'
import { Mail, ArrowLeft, CheckCircle } from 'lucide-react'

export default function ForgotPassword() {
  const [email, setEmail] = useState('')
  const [loading, setLoading] = useState(false)
  const [sent, setSent] = useState(false)
  const { error: showError } = useToast()

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      showError('Некорректный формат email')
      return
    }
    setLoading(true)
    try {
      await api.post('/auth/forgot-password', { email })
      setSent(true)
    } catch {
      showError('Не удалось отправить письмо. Попробуйте позже.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white">Восстановление пароля</h2>
        </div>

        {sent ? (
          <div className="card space-y-6 text-center">
            <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
            </div>
            <p className="text-gray-700 dark:text-gray-300">
              Если email есть в системе, мы отправили на него ссылку для сброса пароля. Проверьте
              почту (и папку «Спам»).
            </p>
            <Link to="/login" className="btn-navy inline-flex items-center justify-center">
              <ArrowLeft className="h-4 w-4 mr-2" />
              Ко входу
            </Link>
          </div>
        ) : (
          <form className="card space-y-6" onSubmit={handleSubmit}>
            <p className="text-sm text-gray-600 dark:text-gray-400">
              Укажите email — пришлём ссылку для сброса пароля.
            </p>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Email
              </label>
              <div className="flex items-center border border-gray-300 rounded-lg px-3 bg-white dark:bg-gray-800 dark:border-gray-600 focus-within:ring-2 focus-within:ring-primary-500 transition-all">
                <Mail className="h-5 w-5 text-gray-400 dark:text-gray-500 flex-shrink-0" />
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="flex-1 px-3 py-2.5 bg-transparent outline-none text-gray-900 dark:text-gray-100"
                  placeholder="example@mail.ru"
                />
              </div>
            </div>
            <button
              type="submit"
              disabled={loading}
              className="btn-navy w-full flex items-center justify-center"
            >
              {loading ? 'Отправляем...' : 'Отправить ссылку'}
            </button>
            <div className="text-center text-sm">
              <Link to="/login" className="text-primary-600 dark:text-primary-400 hover:underline">
                Вспомнили пароль? Войти
              </Link>
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
