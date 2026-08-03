import React, { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import api from '../utils/api'
import {
  ArrowLeft,
  Loader2,
  Check,
  AlertCircle,
  Eye,
  ExternalLink,
  Sparkles,
  ChevronDown,
} from 'lucide-react'
import EmbedPicker from '../components/EmbedPicker'

const METHOD_LABELS = {
  'json-ld': 'структурированные данные (JSON-LD)',
  microdata: 'микроразметка (microdata)',
  'embedded-json': 'встроенные данные страницы',
  selectors: 'CSS-селекторы',
}

export default function SelectorsSetup() {
  const { id, competitorId } = useParams()
  const navigate = useNavigate()

  const [url, setUrl] = useState('')
  const [nameSelector, setNameSelector] = useState('')
  const [priceSelector, setPriceSelector] = useState('')
  const [loading, setLoading] = useState(false)
  const [verificationResult, setVerificationResult] = useState(null)
  const [error, setError] = useState('')
  const [competitor, setCompetitor] = useState(null)
  const [competitorLoading, setCompetitorLoading] = useState(true)

  // авто-режим (превью + подтверждение)
  const [autoLoading, setAutoLoading] = useState(false)
  const [preview, setPreview] = useState(null)
  const [saving, setSaving] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [catalogs, setCatalogs] = useState([])
  const [selectedCatalogId, setSelectedCatalogId] = useState(null)

  const normalizedUrl = () => (url.startsWith('http') ? url : `https://${url}`)

  const handleAutoPreview = async () => {
    if (!url) {
      setError('Укажите URL страницы с товарами')
      return
    }
    setAutoLoading(true)
    setError('')
    setPreview(null)
    try {
      const response = await api.post('/analysis/preview-products', { url: normalizedUrl() })
      setPreview(response.data)
      // авто не нашло товары — сразу разворачиваем ручные селекторы
      if (!response.data?.success) {
        setShowManual(true)
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Не удалось получить товары с сайта')
      setShowManual(true)
    } finally {
      setAutoLoading(false)
    }
  }

  const handleAutoConfirm = async () => {
    setSaving(true)
    setError('')
    try {
      if (selectedCatalogId) {
        await api.post(`/analysis/catalog/${selectedCatalogId}/parse`, { url: normalizedUrl() })
      } else {
        await api.post(`/analysis/competitor/${competitorId}/parse`, { url: normalizedUrl() })
      }
      navigate(`/analysis/${id}`)
    } catch (err) {
      setError(err.response?.data?.error || 'Ошибка сохранения товаров')
      setSaving(false)
    }
  }

  useEffect(() => {
    const fetchCompetitor = async () => {
      try {
        setCompetitorLoading(true)
        const response = await api.get(`/analysis/competitor/${competitorId}`)
        const comp = response.data.competitor
        setCompetitor(comp)

        const cats = comp.catalogs || []
        setCatalogs(cats)
        // по умолчанию настраиваем основной (первый) каталог
        const primary = cats[0]
        if (primary) {
          setSelectedCatalogId(primary.id)
          setUrl(primary.url || comp.domain || '')
          if (primary.title_selector) setNameSelector(primary.title_selector)
          if (primary.price_selector) setPriceSelector(primary.price_selector)
        } else {
          if (comp.domain) setUrl(comp.domain)
          if (comp.title_selector) setNameSelector(comp.title_selector)
          if (comp.price_selector) setPriceSelector(comp.price_selector)
        }
      } catch (err) {
        setError(err.response?.data?.error || 'Ошибка загрузки данных конкурента')
      } finally {
        setCompetitorLoading(false)
      }
    }

    if (competitorId) {
      fetchCompetitor()
    }
  }, [competitorId])

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
        price_selector: priceSelector,
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
      const payload = {
        url: url.startsWith('http') ? url : `https://${url}`,
        title_selector: nameSelector,
        price_selector: priceSelector,
      }
      if (selectedCatalogId) {
        await api.post(`/analysis/catalog/${selectedCatalogId}/parse`, payload)
      } else {
        await api.post(`/analysis/competitor/${competitorId}/parse`, payload)
      }
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
                ? 'Добавление товаров с вашего сайта'
                : 'Добавление товаров конкурента'}
            </h1>
            <p className="text-gray-600 dark:text-gray-400 mb-6">
              Вставьте ссылку на страницу с товарами — мы попробуем определить товары и
              цены автоматически. Селекторы нужны, только если автоопределение не сработает.
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
          {catalogs.length > 1 && (
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Каталог
              </label>
              <select
                value={selectedCatalogId ?? ''}
                onChange={(e) => {
                  const cid = Number(e.target.value)
                  const cat = catalogs.find((c) => c.id === cid)
                  setSelectedCatalogId(cid)
                  setUrl(cat?.url || '')
                  setNameSelector(cat?.title_selector || '')
                  setPriceSelector(cat?.price_selector || '')
                  setPreview(null)
                  setVerificationResult(null)
                  setError('')
                }}
                className="input-field"
              >
                {catalogs.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name || c.url} ({c.products_count}{' '}
                    {c.products_count === 1 ? 'товар' : 'товаров'})
                  </option>
                ))}
              </select>
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                Выберите каталог, для которого настраиваете селекторы.
              </p>
            </div>
          )}
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
              Вставьте URL страницы с товарами (для быстрого перехода используйте кнопку «Открыть»)
            </p>
          </div>

          {/* Авто-режим: найти товары по ссылке */}
          <div>
            <button
              onClick={handleAutoPreview}
              disabled={autoLoading || !url}
              className="btn-primary flex items-center space-x-2"
            >
              {autoLoading ? (
                <>
                  <Loader2 className="h-5 w-5 animate-spin" />
                  <span>Ищем товары...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-5 w-5" />
                  <span>Найти товары автоматически</span>
                </>
              )}
            </button>
            <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
              Определим товары и цены по ссылке — селекторы указывать не нужно.
            </p>
          </div>

          {preview && (
            <div
              className={`border rounded-lg p-6 ${
                preview.success
                  ? 'border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-900/30'
                  : 'border-yellow-300 bg-yellow-50 dark:border-yellow-800 dark:bg-yellow-900/30'
              }`}
            >
              {preview.success ? (
                <React.Fragment>
                  <div className="flex items-center space-x-2 mb-1">
                    <Check className="h-6 w-6 text-green-600 dark:text-green-400" />
                    <h3 className="font-semibold text-green-900 dark:text-green-100">
                      Найдено товаров: {preview.count}
                    </h3>
                  </div>
                  <p className="text-xs text-gray-500 dark:text-gray-400 mb-4">
                    Способ: {METHOD_LABELS[preview.method] || preview.method}
                  </p>
                  <div className="max-h-72 overflow-auto rounded border dark:border-gray-700 divide-y dark:divide-gray-700 bg-white dark:bg-gray-800">
                    {preview.products.map((p, i) => (
                      <div key={i} className="flex items-center justify-between px-3 py-2 text-sm">
                        {p.url ? (
                          <a
                            href={p.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            title={p.name}
                            className="text-gray-700 dark:text-gray-300 truncate pr-3 hover:underline hover:text-primary-600 dark:hover:text-primary-400"
                          >
                            {p.name}
                          </a>
                        ) : (
                          <span className="text-gray-700 dark:text-gray-300 truncate pr-3">
                            {p.name}
                          </span>
                        )}
                        <span className="font-semibold text-gray-900 dark:text-white whitespace-nowrap">
                          {Math.round(p.price)} {p.currency === 'RUB' ? '₽' : p.currency}
                        </span>
                      </div>
                    ))}
                  </div>
                  {preview.count > preview.products.length && (
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-2">
                      Показаны первые {preview.products.length} из {preview.count}.
                    </p>
                  )}
                  <button
                    onClick={handleAutoConfirm}
                    disabled={saving}
                    className="btn-primary flex items-center space-x-2 mt-4"
                  >
                    {saving ? (
                      <>
                        <Loader2 className="h-5 w-5 animate-spin" />
                        <span>Сохраняем...</span>
                      </>
                    ) : (
                      <>
                        <Check className="h-5 w-5" />
                        <span>Подтвердить и собрать</span>
                      </>
                    )}
                  </button>
                </React.Fragment>
              ) : (
                <div className="flex items-start space-x-2">
                  <AlertCircle className="h-6 w-6 text-yellow-600 dark:text-yellow-400" />
                  <div>
                    <h3 className="font-semibold text-yellow-900 dark:text-yellow-100">
                      Автоматически найти не удалось
                    </h3>
                    <p className="text-sm text-yellow-700 dark:text-yellow-300 mt-1">
                      Похоже, на сайте нет машиночитаемых данных о товарах. Укажите CSS-селекторы
                      вручную ниже.
                    </p>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Визуальный выбор мышкой — только для своего сайта: на чужой сайт
              скрипт поставить нельзя. */}
          {competitor?.is_user_site && (
            <EmbedPicker
              siteUrl={url || competitor?.domain || ''}
              onPick={({ title_selector, price_selector }) => {
                if (title_selector) setNameSelector(title_selector)
                if (price_selector) setPriceSelector(price_selector)
                setShowManual(true)
              }}
            />
          )}

          {/* Ручные селекторы — запасной вариант */}
          <button
            type="button"
            onClick={() => setShowManual((v) => !v)}
            className="flex items-center text-sm text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white"
          >
            <ChevronDown
              className={`h-4 w-4 mr-1 transition-transform ${showManual ? 'rotate-180' : ''}`}
            />
            Указать селекторы вручную
          </button>

          {showManual && (
          <React.Fragment>
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
                Примеры:{' '}
                <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">.product-title</code>,{' '}
                <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">#item-name</code>
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
                Примеры: <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">.price</code>,{' '}
                <code className="bg-gray-100 dark:bg-gray-800 px-1 rounded">
                  [itemprop=&quot;price&quot;]
                </code>
              </p>
            </div>
          </div>

          <div className="bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 rounded-lg p-4">
            <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">
              Как найти селектор?
            </h4>
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
            <div
              className={`border rounded-lg p-6 ${
                verificationResult.valid
                  ? 'border-green-300 bg-green-50 dark:border-green-800 dark:bg-green-900/30'
                  : 'border-red-300 bg-red-50 dark:border-red-800 dark:bg-red-900/30'
              }`}
            >
              <div className="flex items-center space-x-2 mb-4">
                {verificationResult.valid ? (
                  <Check className="h-6 w-6 text-green-600 dark:text-green-400" />
                ) : (
                  <AlertCircle className="h-6 w-6 text-red-600 dark:text-red-400" />
                )}
                <h3
                  className={`font-semibold ${
                    verificationResult.valid
                      ? 'text-green-900 dark:text-green-100'
                      : 'text-red-900 dark:text-red-100'
                  }`}
                >
                  {verificationResult.valid ? 'Селекторы найдены!' : 'Селекторы не найдены'}
                </h3>
              </div>

              {verificationResult.mismatch_warning && (
                <div className="mb-4 p-3 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-lg flex items-start space-x-2">
                  <AlertCircle className="h-5 w-5 text-yellow-600 dark:text-yellow-400 mt-0.5" />
                  <p className="text-sm text-yellow-700 dark:text-yellow-300">
                    {verificationResult.mismatch_message}
                  </p>
                </div>
              )}

              {verificationResult.product_count !== undefined && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Будет собрано товаров:
                  </p>
                  <p className="text-3xl font-bold text-gray-900 dark:text-white">
                    {verificationResult.product_count}
                  </p>
                </div>
              )}

              <div className="grid md:grid-cols-2 gap-4 mb-4">
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Совпадений названий:
                  </p>
                  <p className="text-2xl font-bold text-gray-500 dark:text-gray-400">
                    {verificationResult.name_count}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Совпадений цен:
                  </p>
                  <p className="text-2xl font-bold text-gray-500 dark:text-gray-400">
                    {verificationResult.price_count}
                  </p>
                </div>
              </div>

              {verificationResult.sample_names?.length > 0 && (
                <div className="mb-4">
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Примеры названий:
                  </p>
                  <div className="space-y-1">
                    {verificationResult.sample_names.slice(0, 3).map((name, i) => (
                      <p
                        key={i}
                        className="text-sm text-gray-600 dark:text-gray-400 bg-white dark:bg-gray-800 px-3 py-2 rounded border dark:border-gray-700"
                      >
                        {name.length > 60 ? name.substring(0, 60) + '...' : name}
                      </p>
                    ))}
                  </div>
                </div>
              )}

              {verificationResult.sample_prices?.length > 0 && (
                <div>
                  <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Примеры цен:
                  </p>
                  <div className="flex flex-wrap gap-2">
                    {verificationResult.sample_prices.slice(0, 5).map((price, i) => (
                      <span
                        key={i}
                        className="text-sm bg-white dark:bg-gray-800 px-3 py-2 rounded border dark:border-gray-700"
                      >
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
          </React.Fragment>
          )}
        </div>
      </div>
    </div>
  )
}
