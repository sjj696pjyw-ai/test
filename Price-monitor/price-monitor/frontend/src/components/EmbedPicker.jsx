import { useState, useEffect, useRef } from 'react'
import { Code2, RefreshCw, Check, ChevronDown, ChevronUp, ExternalLink } from 'lucide-react'
import api from '../utils/api'
import { formatPrice } from '../utils/export'
import { useToast } from '../context/ToastContext'

/**
 * Визуальный выбор блоков товаров на СВОЁМ сайте.
 *
 * Пользователь ставит скрипт на свой сайт, открывает страницу каталога с
 * меткой ?pm-pick=1, кликает по названию товара и по цене — селекторы
 * определяются автоматически и приходят сюда.
 *
 * Компонент показывается только для своего сайта: на чужой сайт скрипт
 * поставить нельзя, и предлагать это бессмысленно.
 *
 * props:
 *   onPick({ title_selector, price_selector }) — выбран блок
 *   defaultOpen — раскрыть сразу
 */
export default function EmbedPicker({ onPick, defaultOpen = false, siteUrl = '' }) {
  const { success, error: showError } = useToast()
  const [open, setOpen] = useState(defaultOpen)
  const [site, setSite] = useState(null)
  const [loading, setLoading] = useState(false)
  const [pageUrl, setPageUrl] = useState(siteUrl)
  const [waiting, setWaiting] = useState(false)   // ждём выбор из вкладки сайта
  const timerRef = useRef(null)

  const load = async (silent = false) => {
    if (!silent) setLoading(true)
    try {
      const resp = await api.get('/embed/site')
      setSite(resp.data.site)
      return resp.data.site
    } catch {
      if (!silent) showError('Не удалось получить данные подключения')
      return null
    } finally {
      if (!silent) setLoading(false)
    }
  }

  useEffect(() => {
    if (open && !site) load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Пока пользователь выбирает блоки в соседней вкладке, сами опрашиваем
  // сервер — возвращаться и нажимать «Проверить» не нужно.
  useEffect(() => {
    if (!waiting) return
    const started = Date.now()
    timerRef.current = setInterval(async () => {
      const fresh = await load(true)
      const gotPick = fresh?.blocks?.length
      if (gotPick || Date.now() - started > 5 * 60 * 1000) {
        setWaiting(false)
        if (gotPick) success('Выбор получен с вашего сайта')
      }
    }, 3000)
    return () => clearInterval(timerRef.current)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [waiting])

  useEffect(() => () => clearInterval(timerRef.current), [])

  // Открывает страницу каталога в новой вкладке сразу в режиме выбора —
  // адрес править не нужно.
  const openPicker = () => {
    let u = (pageUrl || '').trim()
    if (!u) {
      showError('Укажите адрес страницы каталога')
      return
    }
    if (!/^https?:\/\//i.test(u)) u = 'https://' + u
    u += (u.includes('?') ? '&' : '?') + 'pm-pick=1'
    window.open(u, '_blank', 'noopener')
    setWaiting(true)
  }

  const snippet = site
    ? `<script src="${window.location.origin}/embed/pm.js?key=${site.key}" async></script>`
    : ''

  const blocks = site?.blocks || []

  return (
    <div>
      <button
        onClick={() => setOpen((v) => !v)}
        className="text-sm text-primary-600 dark:text-primary-400 hover:underline flex items-center gap-1"
      >
        {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
        <Code2 className="h-4 w-4" />
        Выбрать товары мышкой на своём сайте
      </button>


      {open && (
        <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-700/40 rounded-lg space-y-3">
          {loading && !site ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Загрузка…</p>
          ) : (
            <>
              <p className="text-xs text-gray-600 dark:text-gray-400">
                1. Один раз вставьте этот код на страницы своего сайта (перед{' '}
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
                2. Укажите страницу каталога и нажмите кнопку — она откроется в новой
                вкладке сразу в режиме выбора. Наведите мышь на <b>название товара</b> и
                кликните, затем кликните по <b>цене</b>. Возвращаться сюда и что-то нажимать
                не нужно: результат появится ниже сам.
              </p>
              <div className="flex gap-2">
                <input
                  type="text"
                  value={pageUrl}
                  onChange={(e) => setPageUrl(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && openPicker()}
                  placeholder="https://ваш-сайт.ru/catalog/"
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 text-sm focus:outline-none focus:ring-2 focus:ring-primary-500"
                />
                <button
                  onClick={openPicker}
                  className="btn-primary text-sm flex items-center gap-1 shrink-0"
                >
                  <ExternalLink className="h-4 w-4" />
                  Открыть и выбрать
                </button>
              </div>
              <p className="text-xs text-gray-500 dark:text-gray-500">
                Обычные посетители сайта ничего не видят и никаких данных не отправляют.
              </p>

              <div className="flex items-center gap-2">
                {waiting ? (
                  <span className="text-xs text-primary-600 dark:text-primary-400 flex items-center gap-1">
                    <RefreshCw className="h-3 w-3 animate-spin" />
                    Ждём ваш выбор на сайте…
                  </span>
                ) : (
                  <button
                    onClick={() => load()}
                    disabled={loading}
                    className="btn-secondary text-xs flex items-center gap-1"
                  >
                    <RefreshCw className={`h-3 w-3 ${loading ? 'animate-spin' : ''}`} />
                    Проверить
                  </button>
                )}
                {site?.connected ? (
                  <span className="text-xs text-green-600 dark:text-green-400">
                    Данные получены: {site.domain || 'сайт'}
                  </span>
                ) : (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    Выбор со скрипта ещё не приходил
                  </span>
                )}
              </div>

              {blocks.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-medium text-gray-700 dark:text-gray-300">
                    3. Ваш выбор — примените его:
                  </p>
                  {blocks.map((b, i) => (
                    <div
                      key={i}
                      className="border border-gray-200 dark:border-gray-600 rounded-md p-2 bg-white dark:bg-gray-800"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-xs text-gray-700 dark:text-gray-300">
                          <b>{b.count}</b> товаров · <code>{b.title_selector}</code> /{' '}
                          <code>{b.price_selector}</code>
                        </span>
                        <button
                          onClick={() => {
                            onPick?.({
                              title_selector: b.title_selector,
                              price_selector: b.price_selector,
                            })
                            success('Селекторы подставлены')
                          }}
                          className="btn-primary text-xs py-1 px-2 flex items-center gap-1 shrink-0"
                        >
                          <Check className="h-3 w-3" />
                          Применить
                        </button>
                      </div>
                      <div className="mt-1 space-y-0.5">
                        {(b.samples || []).slice(0, 3).map((s, j) => (
                          <div
                            key={j}
                            className="flex items-center justify-between text-xs text-gray-600 dark:text-gray-400"
                          >
                            <span className="truncate">{s.name}</span>
                            <span className="shrink-0 ml-2">
                              {s.price != null ? formatPrice(s.price) : '—'}
                            </span>
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
    </div>
  )
}
