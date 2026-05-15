import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { User, Mail, Calendar, AlertCircle } from 'lucide-react'
import { formatDate } from '../utils/export'
import { useToast } from '../context/ToastContext'

export default function Profile() {
  const { user, logout } = useAuth()
  const { success, error: showError } = useToast()
  const navigate = useNavigate()
  const [showConfirm, setShowConfirm] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="max-w-2xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-gray-100 mb-8">Профиль</h1>

      <div className="card">
        <div className="flex items-center space-x-4 mb-6 pb-6 border-b border-gray-200 dark:border-gray-700">
          <div className="w-16 h-16 bg-primary-100 dark:bg-primary-900 rounded-full flex items-center justify-center">
            <User className="h-8 w-8 text-primary-600 dark:text-primary-400" />
          </div>
          <div>
            <h2 className="text-xl font-semibold text-gray-900 dark:text-gray-100">Аккаунт пользователя</h2>
            <p className="text-gray-500 dark:text-gray-400">Управление профилем</p>
          </div>
        </div>

        <div className="space-y-4">
          <div className="flex items-center space-x-3">
            <Mail className="h-5 w-5 text-gray-400 dark:text-gray-500" />
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Email</p>
              <p className="font-medium text-gray-900 dark:text-gray-100">{user?.email}</p>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <Calendar className="h-5 w-5 text-gray-400 dark:text-gray-500" />
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Дата регистрации</p>
              <p className="font-medium text-gray-900 dark:text-gray-100">
                {user?.created_at ? formatDate(user.created_at) : 'N/A'}
              </p>
            </div>
          </div>
        </div>



        <div className="mt-8 pt-6 border-t border-gray-200 dark:border-gray-700">
          <h3 className="font-medium text-gray-900 dark:text-gray-100 mb-4">Безопасность</h3>
          
          {showConfirm ? (
            <div className="p-4 bg-red-50 dark:bg-red-900/30 rounded-lg">
              <div className="flex items-start space-x-3">
                <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5" />
                <div>
                  <p className="text-sm text-red-700 dark:text-red-300 font-medium">Вы уверены?</p>
                  <p className="text-sm text-red-600 dark:text-red-400 mt-1">
                    Это действие завершит текущую сессию.
                  </p>
                </div>
              </div>
              <div className="flex space-x-3 mt-4">
                <button
                  onClick={() => setShowConfirm(false)}
                  className="btn-secondary text-sm"
                >
                  Отмена
                </button>
                <button
                  onClick={handleLogout}
                  className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 text-sm dark:bg-red-700 dark:hover:bg-red-800"
                >
                  Выйти
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowConfirm(true)}
              className="text-red-600 hover:text-red-700 text-sm font-medium dark:text-red-400 dark:hover:text-red-300"
            >
              Выйти из аккаунта
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
