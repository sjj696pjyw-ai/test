import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'

const STORAGE_KEY = 'pm_cookie_consent'

export default function CookieBanner() {
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    try {
      if (!localStorage.getItem(STORAGE_KEY)) setVisible(true)
    } catch {
      setVisible(true)
    }
  }, [])

  const accept = () => {
    try {
      localStorage.setItem(STORAGE_KEY, new Date().toISOString())
    } catch {
      // localStorage недоступен — просто скрываем баннер
    }
    setVisible(false)
  }

  if (!visible) return null

  return (
    <div className="fixed bottom-0 inset-x-0 z-[90] p-3 sm:p-4">
      <div className="max-w-4xl mx-auto bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl shadow-lg p-4 flex flex-col sm:flex-row sm:items-center gap-3">
        <p className="text-sm text-gray-600 dark:text-gray-300 flex-1">
          Мы используем файлы cookie для работы сервиса и улучшения его качества. Продолжая
          пользоваться сайтом, вы соглашаетесь с обработкой cookie и{' '}
          <Link
            to="/privacy"
            className="text-primary-600 dark:text-primary-400 hover:underline whitespace-nowrap"
          >
            Политикой конфиденциальности
          </Link>
          .
        </p>
        <button onClick={accept} className="btn-primary text-sm shrink-0 self-start sm:self-auto">
          Принять
        </button>
      </div>
    </div>
  )
}
