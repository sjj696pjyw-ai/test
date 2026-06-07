import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../utils/api'
import { ArrowLeft, Loader2, Check, AlertCircle, Eye, ExternalLink } from 'lucide-react'
import { useToast } from '../context/ToastContext'

export default function SelectorsSetup() {
  const { id, competitorId } = useParams()
  const navigate = useNavigate()
  const { error: showError } = useToast()

  const [url, setUrl] = useState('')
  const [nameSelector, setNameSelector] = useState('')
  const [priceSelector, setPriceSelector] = useState('')
  const [loading, setLoading] = useState(false)
  const [verificationResult, setVerificationResult] = useState(null)
  const [error, setError] = useState('')
  const [competitor, setCompetitor] = useState(null)
  const [competitorLoading, setCompetitorLoading] = useState(true)

  useEffect(() => {
    const fetchCompetitor = async () => {
      try {
        setCompetitorLoading(true)
        const response = await api.get(`/analysis/competitor/${competitorId}`)
        const comp = response.data.competitor
        setCompetitor(comp)
        // Подставляем текущий сайт в поле ссылки — его можно изменить на новый
        if (comp.domain) setUrl(comp.domain)
        if (comp.title_selector) setNameSelector(comp.title_selector)
        if (comp.price_selector) setPriceSelector(comp.price_selector)
      } catch (err) {
        setError(err.response?.data?.error || 'Ошибка загрузки данных конкурента')
      } finally {
        setCompetitorLoading(false)
      }
    }

    if (competitorId) {
      fetchCompetitor()
    }
  }, [competitorId, api])

  const handleVerify = async () => {
    if (!url || !nameSelector || !priceSelector) {
      setError('Заполните URL и оба селектора')
      return
    }

    setLoading(true)
    setError('')
    setVerificationResult(null)

    try {
      const response = await api.post(`/analysis/competitor/${competitorId}/verify-selectors`, {
        url: url.startsWith('http') ? url : `https://${url}`,
        title_selector: nameSelector,
        price_selector: priceSelector
      })
      setVerificationResult(response.data)
    } catch (err) {
      setError(err.response?.data?.error || 'Ошибка проверки селекторов')
    } finally {
      setLoading(false)
    }
  }

  const handleParse = async () => {
    if (!verificationResult?.valid) {
      setError('Сначала проверьте и сохраните селекторы')
      return
    }

    setLoading(true)

    try {
      await api.post(`/analysis/competitor/${competitorId}/parse`, {
        url: url.startsWith('http') ? url : `https://${url}`,
        title_selector: nameSelector,
        price_selector: priceSelector
      })
      navigate(`/analysis/${id}`)
    } catch (err) {
      setError(err.response?.data?.error || 'Ошибка парсинга')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <button
        onClick={() => navigate(`/analysis/${id}`)}
        className="flex items-center text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-6"
      >
        <ArrowLeft className="h-4 w-4 mr-1" />
        Назад к анализу
      </button>

      <div className="card">
        {competitorLoading ? (
          <div className="text-center py-8">
            <p className="text-gray-600 dark:text-gray-400">Загрузка данных...</p>
          </div>
        ) : (
          <React.Fragment>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">
              {competitor && competitor.is_user_site
                ? 'Настройка селекторов для вашего сайта'
                : 'Настройка селекторов'}
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              {competitor && competitor.is_user_site
                ? 'Укажите CSS-селекторы для названия товара и цены на вашем сайте'
                : 'Укажите CSS-селекторы для названия товара и цены на сайте конкурента'}
            </p>
          </React.Fragment>
        )}

        {error && (
          <div className="mb-6 p-4 bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 rounded-lg flex items-start space-x-3">
            <AlertCircle className="h-5 w-5 text-red-600 dark:text-red-400 mt-0.5" />
            <div>
              <p className="text-red-700 dark:text-red-300 font-medium">Ошибка</p>
              <p className="text-red-600 dark:text-red-400 text-sm">{error}</p>
            </div>
          </div>
        )}

        <div className="space-y-6">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
              URL страницы с товарами
            </label>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                className="input-field flex-1"
                placeholder="https://example.ru/catalog"
              />
              {url && (
                <a
                  href={url.startsWith('http') ? url : `https://${url}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="btn-secondary flex items-center space-x-1 whitespace-nowrap"
                >
                  <ExternalLink className="h-4 w-4" />
                  <span>Открыть</span>
                </a>
              )}
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              Вставьте URL страницы с товарами (для быстрого перехода используйте кнопку "Открыть")
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Селектор названия товара
              </label>
              <input
                type="text"
                value={nameSelector}
                onChange={(e) => setNameSelector(e.target.value)}
                className="input-field font-mono text-sm"
                placeholder=".product-name, #item-title, h2"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Примеры: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">.product-title</code>, <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">#item-name</code>
              </p>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Селектор цены
              </label>
              <input
                type="text"
                value={priceSelector}
                onChange={(e) => setPriceSelector(e.target.value)}
                className="input-field font-mono text-sm"
                placeholder=".price, #product-price, span.price"
              />
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Примеры: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">.price</code>, <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">[itemprop="price"]</code>
              </p>
            </div>
          </div>



          <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">Как найти селектор?</h4>
            <ol className="text-sm text-blue-800 dark:text-blue-200 space-y-1 list-decimal list-inside">
              <li>Откройте сайт конкурента в браузере</li>
              <li>Нажмите F12 или правой кнопкой мыши → Исследовать элемент</li>
              <li>Найдите элемент с названием товара или ценой</li>
              <li>Скопируйте class или id выбранного элемента</li>
            </ol>
          </div>

          <button
            onClick={handleVerify}
            disabled={loading || !url || !nameSelector || !priceSelector}
            className="btn-primary flex items-center space-x-2"
          >
            {loading ? (
              <>
                <Loader2 className="h-5 w-5 animate-spin" />
                <span>Проверка...</span>
              </>
            ) : (
              <>
                <Eye className="h-5 w-5" />
                <span>Проверить селекторы</span>
              </>
            )}
          </button>

          {verificationResult && (
            <div className={`border rounded-lg p-6 ${verificationResult.valid
              ? 'border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-900/30'
              : 'border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-900/30'
              }`}>
              <div className="flex items-center space-x-2 mb-4">
                {verificationResult.valid ? (
                  <Check className="h-6 w-6 text-green-600 dark:text-green-400" />
                ) : (
                  <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
                )}
                <h3 className={`font-semibold ${verificationResult.valid ? 'text-green-900 dark:text-green-100' : 'text-red-900 dark:text-red-100'
                  }`}>
                  {verificationResult.valid ? 'Селекторы найдены!' : 'Селекторы не найдены'}
                </h3>
              </div>

              {verificationResult.mismatch_warning && (
                <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-lg flex items-start space-x-2">
                  <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
                  <p className="text-sm text-yellow-700 dark:text-yellow-300">{verificationResult.mismatch_message}</p>
                </div>
              )}

              <div className="grid md:grid-cols-2 gap-4 mb-4">
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Названий товаров:</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{verificationResult.name_count}</p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Цен:</p>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{verificationResult.price_count}</p>
                </div>
              </div>

              {verificationResult.sample_names?.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Примеры названий:</p>
                  <div className="space-y-1">
                    {verificationResult.sample_names.slice(0, 3).map((name, i) => (
                      <p key={i} className="text-sm text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 px-3 py-2 rounded border dark:border-gray-700">
                        {name.length > 60 ? name.substring(0, 60) + '...' : name}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {verificationResult.sample_prices?.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Примеры цен:</p>
                  <div className="flex flex-wrap gap-2">
                    {verificationResult.sample_prices.slice(0, 5).map((price, i) => (
                      <span key={i} className="text-sm bg-white dark:bg-gray-800 px-3 py-2 rounded border dark:border-gray-700">
                        {price}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {verificationResult?.valid && (
            <div className="flex flex-col sm:flex-row gap-4">
              <button
                onClick={handleParse}
                disabled={loading}
                className="btn-primary flex items-center justify-center space-x-2"
              >
                <ExternalLink className="h-5 w-5" />
                <span>Сохранить и собрать товары</span>
              </button>
            </div>
          )}

        </div>
      </div>
    </div>
  )
}
