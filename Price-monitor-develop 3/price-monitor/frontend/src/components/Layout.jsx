import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useTheme } from '../context/ThemeContext'
import { BarChart3, LogOut, User, Menu, X, Sun, Moon } from 'lucide-react'
import { useState } from 'react'

export default function Layout({ children }) {
  const { user, logout } = useAuth()
  const { isDark, toggleTheme } = useTheme()
  const navigate = useNavigate()
  const location = useLocation()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const isDemo = location.state?.demo === true

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="min-h-screen flex flex-col bg-gray-50 dark:bg-gray-900 transition-colors">
      <header className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <Link to="/" className="flex items-center space-x-2">
              <BarChart3 className="h-8 w-8 text-primary-600 dark:text-primary-400" />
              <span className="text-xl font-bold text-gray-900 dark:text-white">PriceMonitor</span>
              {isDemo && (
                <span className="px-2 py-0.5 text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200 rounded-full">
                  Демо
                </span>
              )}
            </Link>

            <nav className="hidden md:flex items-center space-x-8">
              <Link to="/" className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white">Главная</Link>
              {user ? (
                <>
                  <Link to="/dashboard" className="text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white">Мои анализы</Link>
                  <div className="flex items-center space-x-4">
                    <button
                      onClick={toggleTheme}
                      className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                      aria-label="Toggle theme"
                    >
                      {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                    </button>
                    <Link to="/profile" className="flex items-center space-x-1 text-gray-600 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white">
                      <User className="h-4 w-4" />
                      <span className="hidden lg:inline">{user.email}</span>
                    </Link>
                    <button onClick={handleLogout} className="btn-secondary flex items-center space-x-1 text-sm">
                      <LogOut className="h-4 w-4" />
                      <span>Выйти</span>
                    </button>
                  </div>
                </>
              ) : (
                <div className="flex items-center space-x-4">
                  <button
                    onClick={toggleTheme}
                    className="p-2 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    aria-label="Toggle theme"
                  >
                    {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
                  </button>
                  <Link to="/login" className="btn-secondary">Войти</Link>
                  <Link to="/register" className="btn-primary">Регистрация</Link>
                </div>
              )}
            </nav>

            <div className="flex items-center space-x-2 md:hidden">
              <button
                onClick={toggleTheme}
                className="p-2 text-gray-500 dark:text-gray-400 rounded-lg"
              >
                {isDark ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>
              <button 
                className="p-2 text-gray-600 dark:text-gray-300"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                {mobileMenuOpen ? <X className="h-6 w-6" /> : <Menu className="h-6 w-6" />}
              </button>
            </div>
          </div>
        </div>

        {mobileMenuOpen && (
          <div className="md:hidden bg-white dark:bg-gray-800 border-t border-gray-200 dark:border-gray-700">
            <div className="px-4 py-4 space-y-3">
              <Link to="/" className="block text-gray-600 dark:text-gray-300">Главная</Link>
              {user ? (
                <>
                  <Link to="/dashboard" className="block text-gray-600 dark:text-gray-300">Мои анализы</Link>
                  <Link to="/profile" className="block text-gray-600 dark:text-gray-300">Профиль</Link>
                  <button onClick={handleLogout} className="btn-secondary w-full">Выйти</button>
                </>
              ) : (
                <div className="space-y-2">
                  <Link to="/login" className="btn-secondary w-full block text-center">Войти</Link>
                  <Link to="/register" className="btn-primary w-full block text-center">Регистрация</Link>
                </div>
              )}
            </div>
          </div>
        )}
      </header>

      <main className="flex-1">
        {children}
      </main>


    </div>
  )
}
