import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { User, Mail, Calendar, AlertCircle, Lock } from 'lucide-react'
import { formatDate } from '../utils/export'
import { useToast } from '../context/ToastContext'
import api from '../utils/api'

export default function Profile() {
  const { user, logout } = useAuth()
  const { success, error: showError } = useToast()
  const navigate = useNavigate()
  const [showConfirm, setShowConfirm] = useState(false)
  const [showPasswordForm, setShowPasswordForm] = useState(false)
  const [oldPassword, setOldPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [loading, setLoading] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  const handleChangePassword = async (e) => {
    e.preventDefault()
    setLoading(true)

    if (newPassword !== confirmPassword) {
      showError('Новые пароли не совпадают')
      setLoading(false)
      return
    }

    if (newPassword.length < 6) {
      showError('Пароль должен быть не менее 6 символов')
      setLoading(false)
      return
    }

    try {
      await api.post('/auth/change-password', {
        old_password: oldPassword,
        new_password: newPassword
      })
      success('Пароль успешно изменён')
      setOldPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setShowPasswordForm(false)
    } catch (error) {
      showError(error.response?.data?.error || 'Ошибка при смене пароля')
    } finally {
      setLoading(false)
    }
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

          {showPasswordForm ? (
            <form onSubmit={handleChangePassword} className="space-y-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Старый пароль
                </label>
                <input
                  type="password"
                  value={oldPassword}
                  onChange={(e) => setOldPassword(e.target.value)}
                  className="input-field"
                  placeholder="Введите старый пароль"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Новый пароль
                </label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="input-field"
                  placeholder="Введите новый пароль"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Подтвердите новый пароль
                </label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="input-field"
                  placeholder="Повторите новый пароль"
                  required
                />
              </div>
              <div className="flex space-x-3 pt-2">
                <button
                  type="button"
                  onClick={() => {
                    setShowPasswordForm(false)
                    setOldPassword('')
                    setNewPassword('')
                    setConfirmPassword('')
                  }}
                  className="btn-secondary text-sm"
                >
                  Отмена
                </button>
                <button
                  type="submit"
                  disabled={loading}
                  className="btn-primary text-sm flex items-center space-x-2"
                >
                  {loading ? (
                    <><span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></span><span>Сохранение...</span></>
                  ) : (
                    <><Lock className="h-4 w-4" /><span>Обновить пароль</span></>
                  )}
                </button>
              </div>
            </form>
          ) : (
            <div className="space-y-3">
              <button
                onClick={() => setShowPasswordForm(true)}
                className="flex items-center space-x-2 text-primary-600 hover:text-primary-700 text-sm font-medium dark:text-primary-400 dark:hover:text-primary-300"
              >
                <Lock className="h-4 w-4" />
                <span>Сменить пароль</span>
              </button>
              <div className="pt-3 border-t border-gray-100 dark:border-gray-700">
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
          )}
        </div>
      </div>
    </div>
  )
}
