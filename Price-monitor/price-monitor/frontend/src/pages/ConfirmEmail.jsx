import { useState, useEffect, useRef } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import api from '../utils/api'
import { CheckCircle, AlertCircle, Loader2 } from 'lucide-react'

export default function ConfirmEmail() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const { confirmEmail } = useAuth()
  const navigate = useNavigate()

  const [status, setStatus] = useState('loading') // loading | success | error
  const [email, setEmail] = useState('')
  const [resending, setResending] = useState(false)
  const done = useRef(false)

  useEffect(() => {
    if (done.current) return
    done.current = true
    if (!token) {
      setStatus('error')
      return
    }
    confirmEmail(token)
      .then(() => {
        setStatus('success')
        setTimeout(() => navigate('/dashboard'), 1200)
      })
      .catch(() => setStatus('error'))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const handleResend = async () => {
    if (!email) return
    setResending(true)
    try {
      await api.post('/auth/resend-confirmation', { email })
    } finally {
      setResending(false)
    }
  }

  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4">
      <div className="max-w-md w-full card text-center space-y-6">
        {status === 'loading' && (
          <>
            <Loader2 className="h-10 w-10 text-primary-600 animate-spin mx-auto" />
            <p className="text-gray-700 dark:text-gray-300">Подтверждаем email...</p>
          </>
        )}

        {status === 'success' && (
          <>
            <div className="w-16 h-16 bg-green-100 dark:bg-green-900 rounded-full flex items-center justify-center mx-auto">
              <CheckCircle className="h-8 w-8 text-green-600 dark:text-green-400" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">Email подтверждён</h2>
            <p className="text-gray-600 dark:text-gray-400">Перенаправляем в личный кабинет...</p>
          </>
        )}

        {status === 'error' && (
          <>
            <div className="w-16 h-16 bg-red-100 dark:bg-red-900 rounded-full flex items-center justify-center mx-auto">
              <AlertCircle className="h-8 w-8 text-red-600 dark:text-red-400" />
            </div>
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              Ссылка недействительна
            </h2>
            <p className="text-gray-600 dark:text-gray-400">
              Ссылка подтверждения неверна или истекла. Запросите новое письмо.
            </p>
            <div className="flex items-center border border-gray-300 rounded-lg px-3 bg-white dark:bg-gray-800 dark:border-gray-600">
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="flex-1 px-2 py-2.5 bg-transparent outline-none text-gray-900 dark:text-gray-100"
                placeholder="Ваш email"
              />
            </div>
            <button
              onClick={handleResend}
              disabled={resending || !email}
              className="btn-primary w-full"
            >
              {resending ? 'Отправляем...' : 'Отправить письмо повторно'}
            </button>
            <Link to="/login" className="block text-sm text-primary-600 dark:text-primary-400 hover:underline">
              Ко входу
            </Link>
          </>
        )}
      </div>
    </div>
  )
}
