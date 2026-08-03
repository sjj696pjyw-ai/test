import { useState, useEffect } from 'react'
import { X, Search, Plus, ChevronDown, ChevronUp, Code2, RefreshCw, Check } from 'lucide-react'
import api from '../utils/api'
import { formatPrice } from '../utils/export'
import { useToast } from '../context/ToastContext'

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
  // Встраивание скрипта на свой сайт: он присылает найденные блоки товаров,
  // и пользователь выбирает нужный вместо ручного подбора селекторов.
  const [showEmbed, setShowEmbed] = useState(false)
  const [embedSite, setEmbedSite] = useState(null)
  const [embedLoading, setEmbedLoading] = useState(false)

  const loadEmbed = async () => {
    setEmbedLoading(true)
    try {
      const resp = await api.get('/embed/site')
      setEmbedSite(resp.data.site)
    } catch {
      showError('Не удалось получить данные подключения')
    } finally {
      setEmbedLoading(false)
    }
  }

  useEffect(() => {
    if (showEmbed && !embedSite) loadEmbed()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [showEmbed])

  const snippet = embedSite
    ? `<script src="${window.location.origin}/embed/pm.js?key=${embedSite.key}" async></script>`
    : ''

  const useBlock = (block) => {
    if (block.title_selector) setTitleSelector(block.title_selector)
    if (block.price_selector) setPriceSelector(block.price_selector)
    setShowManual(true)
    success('Селекторы подставлены из выбранного блока')
  }

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

        {/* Подключение скрипта к своему сайту: он сам находит блоки товаров,
            и остаётся только выбрать нужный. */}
        <button
          onClick={() => setShowEmbed((v) => !v)}
          className="mt-4 text-sm text-primary-600 dark:text-primary-400 hover:underline flex items-center gap-1"
        >
          {showEmbed ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
          <Code2 className="h-4 w-4" />
          Подключить свой сайт скриптом
        </button>

        {showEmbed && (
          <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-700/40 rounded-lg space-y-3">
            {embedLoading && !embedSite ? (
              <p className="text-sm text-gray-500 dark:text-gray-400">Загрузка…</p>
            ) : (
              <>
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  1. Вставьте этот код на страницы своего сайта (перед{' '}
                  <code>&lt;/body&gt;</code>):
                </p>
                <div className="flex gap-2">
                  <code className="flex-1 text-xs bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-600 rounded p-2 break-all text-gray-800 dark:text-gray-200">
                    {snippet}
                  </code>
                  <button
                    onClick={() => {
                      navigator.clipboard?.writeText(snippet)
                      success('Код скопирован')
                    }}
                    className="btn-secondary text-xs shrink-0 self-start"
                  >
                    Копировать
                  </button>
                </div>
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  2. Откройте нужную страницу каталога с одной из меток в адресе:
                </p>
                <ul className="text-xs text-gray-600 dark:text-gray-400 space-y-1 pl-1">
                  <li>
                    <code>?pm-pick=1</code> — <b>визуальный выбор</b>: наводите мышь, блоки
                    подсвечиваются, кликаете по названию товара и по цене.
                  </li>
                  <li>
                    <code>?pm-scan=1</code> — автоматический разбор: скрипт сам найдёт
                    повторяющиеся блоки и предложит варианты.
                  </li>
                </ul>
                <p className="text-xs text-gray-500 dark:text-gray-500">
                  Обычные посетители сайта ничего не отправляют и интерфейса не видят.
                </p>

                <div className="flex items-center gap-2">
                  <button
                    onClick={loadEmbed}
                    disabled={embedLoading}
                    className="btn-secondary text-xs flex items-center gap-1"
                  >
                    <RefreshCw className={`h-3 w-3 ${embedLoading ? 'animate-spin' : ''}`} />
                    Проверить
                  </button>
                  {embedSite?.connected ? (
                    <span className="text-xs text-green-600 dark:text-green-400">
                      Подключено: {embedSite.domain || 'сайт'}
                    </span>
                  ) : (
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      Данных со скрипта ещё не было
                    </span>
                  )}
                </div>

                {embedSite?.blocks?.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
                      3. Найденные блоки товаров — выберите нужный:
                    </p>
                    {embedSite.blocks.map((b, i) => (
                      <div
                        key={i}
                        className="border border-gray-200 dark:border-gray-600 rounded-md p-2 bg-white dark:bg-gray-800"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <span className="text-xs text-gray-700 dark:text-gray-300">
                            {b.picked && (
                              <span className="mr-1 px-1.5 py-0.5 rounded bg-primary-100 dark:bg-primary-900/50 text-primary-700 dark:text-primary-300">
                                выбрано вами
                              </span>
                            )}
                            <b>{b.count}</b> блоков · <code>{b.card_selector}</code>
                          </span>
                          <button
                            onClick={() => useBlock(b)}
                            className="btn-primary text-xs py-1 px-2 flex items-center gap-1 shrink-0"
                          >
                            <Check className="h-3 w-3" />
                            Выбрать
                          </button>
                        </div>
                        <div className="mt-1 space-y-0.5">
                          {(b.samples || []).slice(0, 3).map((s, j) => (
                            <div
                              key={j}
                              className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400"
                            >
                              <span className="truncate">{s.name}</span>
                              <span className="shrink-0 ml-2">{formatPrice(s.price)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
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
