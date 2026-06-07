import { createContext, useContext, useState, useCallback } from 'react'
import { X, CheckCircle, AlertCircle, Info, AlertTriangle } from 'lucide-react'

const ToastContext = createContext(null)

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])

  const addToast = useCallback((message, type = 'info', duration = 4000) => {
    const id = Date.now()
    setToasts(prev => [...prev, { id, message, type }])
    
    if (duration > 0) {
      setTimeout(() => {
        removeToast(id)
      }, duration)
    }
  }, [])

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(toast => toast.id !== id))
  }, [])

  const success = useCallback((message) => addToast(message, 'success'), [addToast])
  const error = useCallback((message) => addToast(message, 'error'), [addToast])
  const warning = useCallback((message) => addToast(message, 'warning'), [addToast])
  const info = useCallback((message) => addToast(message, 'info'), [addToast])

  return (
    <ToastContext.Provider value={{ addToast, removeToast, success, error, warning, info }}>
      {children}
      <ToastContainer toasts={toasts} removeToast={removeToast} />
    </ToastContext.Provider>
  )
}

export function useToast() {
  const context = useContext(ToastContext)
  if (!context) {
    throw new Error('useToast must be used within ToastProvider')
  }
  return context
}

function ToastContainer({ toasts, removeToast }) {
  if (toasts.length === 0) return null

  const icons = {
    success: <CheckCircle className="h-5 w-5" />,
    error: <AlertCircle className="h-5 w-5" />,
    warning: <AlertTriangle className="h-5 w-5" />,
    info: <Info className="h-5 w-5" />
  }

  const styles = {
    success: 'bg-green-50 text-green-800 border-green-200 dark:bg-green-900 dark:text-green-100 dark:border-green-800',
    error: 'bg-red-50 text-red-800 border-red-200 dark:bg-red-900 dark:text-red-100 dark:border-red-800',
    warning: 'bg-yellow-50 text-yellow-800 border-yellow-200 dark:bg-yellow-900 dark:text-yellow-100 dark:border-yellow-800',
    info: 'bg-blue-50 text-blue-800 border-blue-200 dark:bg-blue-900 dark:text-blue-100 dark:border-blue-800'
  }

  const iconStyles = {
    success: 'text-green-600 dark:text-green-400',
    error: 'text-red-600 dark:text-red-400',
    warning: 'text-yellow-600 dark:text-yellow-400',
    info: 'text-blue-600 dark:text-blue-400'
  }

  return (
    <div className="fixed bottom-4 right-4 z-[100] space-y-2 max-w-sm">
      {toasts.map(toast => (
        <div
          key={toast.id}
          className={`flex items-start space-x-3 p-4 rounded-lg border shadow-lg animate-slide-in ${styles[toast.type]}`}
        >
          <span className={iconStyles[toast.type]}>{icons[toast.type]}</span>
          <p className="flex-1 text-sm font-medium">{toast.message}</p>
          <button
            onClick={() => removeToast(toast.id)}
            className="text-gray-400 hover:text-gray-600 dark:text-gray-500 dark:hover:text-gray-300 transition-colors"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      ))}
    </div>
  )
}
