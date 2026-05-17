import { Link } from 'react-router-dom'
import { Mail, ArrowLeft } from 'lucide-react'

export default function ForgotPassword() {
  return (
    <div className="min-h-[80vh] flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h2 className="text-3xl font-bold text-gray-900 dark:text-white">Восстановление пароля</h2>
        </div>

        <div className="card space-y-6 text-center">
          <div className="w-16 h-16 bg-primary-100 dark:bg-primary-900 rounded-full flex items-center justify-center mx-auto">
            <Mail className="h-8 w-8 text-primary-600 dark:text-primary-400" />
          </div>
          
          <p className="text-gray-700 dark:text-gray-300">
            В случае, если вы забыли ваш пароль - напишите на почту{' '}
            <a href="mailto:pricemonitoring_help@mail.ru" className="text-primary-600 dark:text-primary-400 hover:underline font-medium">
              pricemonitoring_help@mail.ru
            </a>{' '}
            для восстановления со своей почты, привязанной к профилю и мы вышлем вам инструкцию для сброса
          </p>

          <Link to="/" className="btn-primary inline-flex items-center justify-center">
            <ArrowLeft className="h-4 w-4 mr-2" />
            На главную
          </Link>
        </div>
      </div>
    </div>
  )
}
