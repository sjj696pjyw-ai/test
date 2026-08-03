import { useState } from 'react'
import { X, Search, Plus, ChevronDown, ChevronUp } from 'lucide-react'
import api from '../utils/api'
import { formatPrice } from '../utils/export'
import { useToast } from '../context/ToastContext'
import EmbedPicker from './EmbedPicker'

// Хост URL без www/схемы/пути.
const hostOf = (url) => {
  let u = (url || '').trim().toLowerCase()
  if (!u) return ''
  if (!/^https?:\/\//.test(u)) u = 'https://' + u
  try {
    const h = new URL(u).hostname
    return h.startsWith('www.') ? h.slice(4) : h
  } catch {
    return ''
  }
}

// Частые двухуровневые публичные суффиксы (site.msk.ru, shop.co.uk).
const MULTI_SUFFIXES = new Set([
  'msk.ru', 'spb.ru', 'com.ru', 'net.ru', 'org.ru', 'edu.ru', 'gov.ru',
  'co.uk', 'org.uk', 'com.ua', 'co.il', 'com.br', 'com.tr', 'com.kz',
  'com.by', 'co.kz',
])

// Регистрируемый («общий») домен: novosibirsk.rus-buket.ru → rus-buket.ru.
const baseDomain = (host) => {
  const h = (host || '').trim().toLowerCase().replace(/^\.+|\.+$/g, '')
  if (!h) return ''
  const parts = h.split('.')
  if (parts.length <= 2) return h
  const last2 = parts.slice(-2).join('.')
  return MULTI_SUFFIXES.has(last2) ? parts.slice(-3).join('.') : last2
}

/**
 * Модалка добавления нового каталога (раздела или карточки того же сайта)
 * к уже добавленному конкуренту.
 *
 * props:
 *   competitor — { id, domain, is_user_site }
 *   onClose() — закрыть
 *   onAdded(catalog) — успешно добавлен каталог (вызвать рефетч)
 */
export default function AddCatalogModal({ competitor, onClose, onAdded }) {
  const { success, error: showError } = useToast()
  const [url, setUrl] = useState('')
  const [preview, setPreview] = useState(null)
  const [loadingPreview, setLoadingPreview] = useState(false)
  const [saving, setSaving] = useState(false)
  const [showManual, setShowManual] = useState(false)
  const [titleSelector, setTitleSelector] = useState('')
  const [priceSelector, setPriceSelector] = useState('')
  const siteHost = hostOf(competitor?.domain)
  const siteBase = baseDomain(siteHost)

  const sameSite = () => {
    const d = baseDomain(hostOf(url))
    return d && siteBase && d === siteBase
  }

  const handlePreview = async () => {
    if (!url.trim()) {
      showError('Укажите ссылку на каталог или карточку товара')
      return
    }
    if (!sameSite()) {
      showError(`Ссылка ведёт на другой сайт (${hostOf(url) || '—'}), а добавлять можно только для ${siteHost}.`)
      return
    }
    setLoadingPreview(true)
    setPreview(null)
    try {
      const resp = await api.post('/analysis/preview-products', { url: url.trim() })
      setPreview(resp.data)
      if (!resp.data?.success) setShowManual(true)
    } catch {
      showError('Не удалось получить товары с сайта')
      setShowManual(true)
    } finally {
      setLoadingPreview(false)
    }
  }

  const handleAdd = async () => {
    if (!url.trim()) {
      showError('Укажите ссылку на каталог или карточку товара')
      return
    }
    // Быстрая клиентская проверка того же сайта (алерт справа снизу).
    if (!sameSite()) {
      showError(`Ссылка ведёт на другой сайт (${hostOf(url) || '—'}), а добавлять можно только для ${siteHost}.`)
      return
    }
    setSaving(true)
    try {
      const resp = await api.post(`/analysis/competitor/${competitor.id}/catalog`, {
        url: url.trim(),
        title_selector: titleSelector.trim() || undefined,
        price_selector: priceSelector.trim() || undefined,
      })
      const count = resp.data?.products?.length || 0
      success(`Каталог добавлен: ${count} ${count === 1 ? 'товар' : 'товаров'}`)
      onAdded?.(resp.data?.catalog)
      onClose?.()
    } catch (err) {
      const code = err.response?.status
      const data = err.response?.data || {}
      // 409 — другой сайт или дубликат; 422 — товары не найдены.
      // Все алерты выводятся тостом справа снизу.
      if (data.message) {
        showError(data.message)
      } else if (code === 409) {
        showError('Эти товары уже были добавлены ранее.')
      } else {
        showError('Не удалось добавить каталог')
      }
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-lg max-w-lg w-full p-6 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between mb-1">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Добавить товары</h3>
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            <X className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          </button>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
          Другой раздел или карточка товара того же сайта{' '}
          <span className="font-medium text-gray-700 dark:text-gray-300">{siteHost}</span>
        </p>

        <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
          Ссылка на каталог или карточку
        </label>
        <div className="flex gap-2">
          <input
            type="text"
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handlePreview()}
            placeholder={`https://${siteHost}/catalog/...`}
            className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
          />
          <button
            onClick={handlePreview}
            disabled={loadingPreview}
            className="btn-secondary flex items-center gap-2 shrink-0"
          >
            {loadingPreview ? (
              <span className="animate-spin rounded-full h-4 w-4 border-2 border-current border-t-transparent" />
            ) : (
              <Search className="h-4 w-4" />
            )}
            <span>Найти</span>
          </button>
        </div>

        {preview && (
          <div className="mt-4">
            {preview.success ? (
              <>
                <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
                  Найдено товаров: <span className="font-semibold">{preview.count}</span>
                </p>
                <div className="space-y-1 max-h-56 overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-lg p-2">
                  {(preview.products || []).slice(0, 50).map((p, i) => (
                    <div
                      key={i}
                      className="flex items-center justify-between text-sm px-2 py-1.5 rounded bg-gray-50 dark:bg-gray-700/50"
                    >
                      <span className="truncate text-gray-900 dark:text-gray-100">{p.name}</span>
                      <span className="shrink-0 ml-3 text-primary-600 dark:text-primary-400 font-medium">
                        {formatPrice(p.price)}
                      </span>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-sm text-yellow-700 dark:text-yellow-400">
                Автоматически найти товары не удалось. Можно указать селекторы вручную ниже.
              </p>
            )}
          </div>
        )}

        {/* Визуальный выбор блоков — только для своего сайта: на чужой сайт
            скрипт поставить нельзя, поэтому и предлагать не нужно. */}
        {competitor?.is_user_site && (
          <div className="mt-4">
            <EmbedPicker
              siteUrl={url || competitor?.domain || ''}
              onPick={({ title_selector, price_selector }) => {
                if (title_selector) setTitleSelector(title_selector)
                if (price_selector) setPriceSelector(price_selector)
                setShowManual(true)
              }}
            />
          </div>
        )}

        <button
          onClick={() => setShowManual((v) => !v)}
          className="mt-4 text-sm text-primary-600 dark:text-primary-400 hover:underline flex items-center gap-1"
        >
          {showManual ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          Указать селекторы вручную
        </button>
        {showManual && (
          <div className="mt-3 space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                Селектор названия (CSS)
              </label>
              <input
                type="text"
                value={titleSelector}
                onChange={(e) => setTitleSelector(e.target.value)}
                placeholder=".product-card__name"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">
                Селектор цены (CSS)
              </label>
              <input
                type="text"
                value={priceSelector}
                onChange={(e) => setPriceSelector(e.target.value)}
                placeholder=".product-card__price"
                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
              />
            </div>

            {/* Та же подсказка, что и на странице настройки селекторов: без неё
                пользователь не понимает, откуда взять эти значения. */}
            <div className="p-3 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
              <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2 text-sm">
                Как найти селектор?
              </h4>
              <ol className="text-xs text-blue-800 dark:text-blue-200 space-y-1 list-decimal list-inside">
                <li>Откройте нужную страницу сайта в браузере</li>
                <li>Нажмите F12 или правой кнопкой мыши → Исследовать элемент</li>
                <li>Найдите элемент с названием товара или ценой</li>
                <li>Скопируйте class или id выбранного элемента</li>
              </ol>
              <p className="text-xs text-blue-800/80 dark:text-blue-200/80 mt-2">
                Примеры: <code>.product-title</code>, <code>#item-name</code>,{' '}
                <code>[itemprop=&quot;price&quot;]</code>
              </p>
            </div>
          </div>
        )}

        <div className="flex justify-end gap-2 mt-6">
          <button onClick={onClose} className="btn-secondary">
            Отмена
          </button>
          <button
            onClick={handleAdd}
            disabled={saving}
            className="btn-primary flex items-center gap-2"
          >
            {saving ? (
              <span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent" />
            ) : (
              <Plus className="h-4 w-4" />
            )}
            <span>Добавить</span>
          </button>
        </div>
      </div>
    </div>
  )
}
