import { useState, useEffect, useMemo, useRef } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import api from '../utils/api'
import { Plus, Calendar, Globe, Trash2, Eye, Search, ChevronLeft, ChevronRight, Filter, X, ChevronDown, RefreshCw, AlertTriangle, ArrowUp, ArrowDown } from 'lucide-react'
import { REGIONS, getRegionName } from '../utils/regions'
import { formatDate } from '../utils/export'
import { AnalysisHistoryChart } from '../components/Charts'

const ITEMS_PER_PAGE = 10

const DEMO_ANALYSES = [
  {
    id: 2,
    analysis_type: 'manual',
    competitors_count: 2,
    created_at: '2026-05-30T09:45:00.000Z',
    region: '2'
  }
]

export default function Dashboard() {
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)
  const [showNewAnalysisModal, setShowNewAnalysisModal] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [selectedRegions, setSelectedRegions] = useState([])
  const [searchQuery, setSearchQuery] = useState('')
  const [showRegionDropdown, setShowRegionDropdown] = useState(false)
  const regionDropdownRef = useRef(null)
  const { user } = useAuth()
  const { success, error: showError, warning } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const isDemo = location.state?.demo === true

  // Лента событий по изменениям цен
  const [events, setEvents] = useState([])
  const [eventsLoading, setEventsLoading] = useState(false)
  const [refreshing, setRefreshing] = useState(false)
  const [problemIds, setProblemIds] = useState([])
  const [eventFrom, setEventFrom] = useState('') // '' = сегодня
  const [eventTo, setEventTo] = useState('')

  useEffect(() => {
    if (isDemo) {
      setAnalyses(DEMO_ANALYSES)
      setLoading(false)
    } else {
      fetchAnalyses()
    }
  }, [isDemo])

  useEffect(() => {
    function handleClickOutside(event) {
      if (regionDropdownRef.current && !regionDropdownRef.current.contains(event.target)) {
        setShowRegionDropdown(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const fetchAnalyses = async () => {
    try {
      const response = await api.get('/analysis')
      setAnalyses(response.data.analyses)
    } catch (error) {
      console.error('Error fetching analyses:', error)
    } finally {
      setLoading(false)
    }
  }

  const fetchEvents = async () => {
    if (isDemo) { setEvents([]); return [] }
    setEventsLoading(true)
    try {
      const params = {}
      if (eventFrom) params.from = eventFrom
      if (eventTo) params.to = eventTo
      const res = await api.get('/analysis/events', { params })
      const list = res.data.events || []
      setEvents(list)
      return list
    } catch (e) {
      console.error('Error fetching events:', e)
      return []
    } finally {
      setEventsLoading(false)
    }
  }

  useEffect(() => {
    if (!isDemo) fetchEvents()
  }, [isDemo, eventFrom, eventTo])

  const handleRefreshAll = async () => {
    if (isDemo) { showError('Обновление недоступно в демо-режиме'); return }
    if (refreshing) return
    setRefreshing(true)
    try {
      const before = events.length
      const res = await api.post('/analysis/update-all-prices')
      const data = res.data
      setProblemIds(data.problem_analysis_ids || [])
      const after = await fetchEvents()
      await fetchAnalyses()
      const newCount = Math.max(0, (after?.length || 0) - before)
      if (data.any_rate_limited) {
        showError('Обновление цен доступно раз в 3 минуты')
      } else if (data.need_selectors) {
        warning('Сначала настройте селекторы у конкурентов — обновлять нечего')
      } else if (data.any_problem) {
        warning('Есть проблемы с обновлением в некоторых анализах')
      } else if (newCount > 0) {
        success(`Цены обновлены. Новых событий: ${newCount}`)
      } else {
        success('Цены обновлены. Новых событий нет')
      }
    } catch (e) {
      console.error('Error refreshing all:', e)
      showError('Не удалось обновить цены')
    } finally {
      setRefreshing(false)
    }
  }

  const deleteAnalysis = async (id) => {
    try {
      await api.delete(`/analysis/${id}`)
      setAnalyses(analyses.filter(a => a.id !== id))
      success('Анализ удалён')
    } catch (error) {
      showError('Ошибка при удалении')
    }
  }

  const availableRegions = useMemo(() => {
    const regionCodes = [...new Set(analyses.map(a => a.region).filter(Boolean))]
    return REGIONS.filter(r => regionCodes.includes(r.value))
  }, [analyses])

  const filteredAnalyses = useMemo(() => {
    return analyses.filter(a => {
      const matchesRegion = selectedRegions.length === 0 || selectedRegions.includes(a.region)
      const searchLower = searchQuery.toLowerCase()
      const matchesSearch = !searchQuery ||
        a.name?.toLowerCase().includes(searchLower)
      return matchesRegion && matchesSearch
    })
  }, [analyses, selectedRegions, searchQuery])

  const totalPages = Math.ceil(filteredAnalyses.length / ITEMS_PER_PAGE)
  const paginatedAnalyses = filteredAnalyses.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  )

  useEffect(() => {
    setCurrentPage(1)
  }, [selectedRegions, searchQuery])

  const toggleRegion = (regionCode) => {
    setSelectedRegions(prev =>
      prev.includes(regionCode)
        ? prev.filter(r => r !== regionCode)
        : [...prev, regionCode]
    )
  }

  const clearRegions = () => {
    setSelectedRegions([])
  }

  // Формируем отображаемый текст для кнопки фильтра регионов
  const getRegionFilterText = () => {
    if (selectedRegions.length === 0) return 'Все регионы'
    const selectedLabels = selectedRegions.map(code => getRegionName(code))
    return selectedLabels.join(', ')
  }

  // Сокращаем текст с троеточием если не помещается
  const getTruncatedRegionText = (text, maxLength = 40) => {
    if (text.length <= maxLength) return text
    return text.substring(0, maxLength - 3) + '...'
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {isDemo && (
        <div className="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/30 border border-yellow-200 dark:border-yellow-700 rounded-lg">
          <div className="flex items-center gap-3">
            <div className="flex-1 text-yellow-800 dark:text-yellow-200">
              <p className="font-medium">Вы в деморежиме</p>
              <p className="text-sm mt-1">Пожалуйста, <Link to="/register" className="underline font-medium">зарегистрируйтесь</Link> для создания реальных анализов и управления ценами.</p>
            </div>
            <Link to="/register" className="px-4 py-2 bg-yellow-600 text-white rounded-lg text-sm font-medium hover:bg-yellow-700 transition-colors whitespace-nowrap">
              Регистрация
            </Link>
          </div>
        </div>
      )}

      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-8 gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Мои анализы</h1>
          <p className="text-gray-600 dark:text-gray-400 mt-1">Управление анализами цен конкурентов</p>
        </div>
        {isDemo ? (
          <button
            onClick={() => showError('Вы в деморежиме. Пожалуйста, зарегистрируйтесь для создания анализов.')}
            className="btn-primary flex items-center space-x-2 opacity-60 cursor-not-allowed"
          >
            <Plus className="h-5 w-5" />
            <span>Новый анализ</span>
          </button>
        ) : (
          <button
            onClick={() => setShowNewAnalysisModal(true)}
            className="btn-primary flex items-center space-x-2"
          >
            <Plus className="h-5 w-5" />
            <span>Новый анализ</span>
          </button>
        )}
      </div>

      {/* События + История анализов */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-8">
        {/* События */}
        <div className="card flex flex-col h-96">
          <div className="flex items-center justify-between gap-3 mb-3 flex-wrap">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white shrink-0">События</h3>
            <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 flex-wrap">
              <input
                type="date"
                value={eventFrom || new Date().toISOString().split('T')[0]}
                onChange={(e) => setEventFrom(e.target.value)}
                className="border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 [color-scheme:light] dark:[color-scheme:dark]"
              />
              <span>—</span>
              <input
                type="date"
                value={eventTo || new Date().toISOString().split('T')[0]}
                onChange={(e) => setEventTo(e.target.value)}
                className="border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 [color-scheme:light] dark:[color-scheme:dark]"
              />
              <button onClick={() => { setEventFrom(''); setEventTo('') }} className="text-primary-600 dark:text-primary-400 hover:underline">Сегодня</button>
              <button onClick={() => { setEventFrom('2000-01-01'); setEventTo(new Date().toISOString().split('T')[0]) }} className="text-primary-600 dark:text-primary-400 hover:underline">За всё время</button>
              <button
                onClick={handleRefreshAll}
                disabled={refreshing || isDemo}
                title="Обновить цены по всем анализам"
                className={`p-2 rounded-lg text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${(refreshing || isDemo) ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                <RefreshCw className={`h-5 w-5 ${refreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>
          </div>

          <div className="flex-1 min-h-0 overflow-y-auto">
            {isDemo ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">События недоступны в демо-режиме</p>
            ) : eventsLoading ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">Загрузка…</p>
            ) : events.length === 0 ? (
              <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-8">За выбранный период событий нет</p>
            ) : (
              <div className="space-y-3">
                {events.map((ev, i) => (
                  <div key={i} className="text-sm text-gray-700 dark:text-gray-300 border-b border-gray-100 dark:border-gray-800 pb-2 last:border-0">
                    <p>
                      В анализе{' '}
                      <Link to={`/analysis/${ev.analysis_id}`} className="text-primary-600 dark:text-primary-400 font-medium hover:underline">{ev.analysis_name}</Link>
                      {' '}у конкурента{' '}
                      <a
                        href={`https://${(ev.competitor_domain || '').replace(/^https?:\/\//, '')}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-primary-600 dark:text-primary-400 hover:underline"
                      >
                        {(ev.competitor_domain || '').replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0]}
                      </a>{' '}
                      {ev.direction === 'decreased' ? 'снизилась' : 'выросла'} цена на «{ev.product_name}»{' '}
                      <span className={`inline-flex items-center gap-0.5 font-medium ${ev.direction === 'decreased' ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                        {ev.direction === 'decreased' ? <ArrowDown className="h-3 w-3" /> : <ArrowUp className="h-3 w-3" />}
                        {Math.round(ev.old_price).toLocaleString('ru-RU')} → {Math.round(ev.new_price).toLocaleString('ru-RU')} ₽
                      </span>.
                      {ev.situational ? ' ' + ev.situational : ''}
                    </p>
                    <p className="text-xs text-gray-400 dark:text-gray-500 mt-0.5">{formatDate(ev.date)}</p>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* История анализов */}
        <div className="card flex flex-col h-96">
          <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">История анализов (7 дней)</h3>
          <div className="flex-1 min-h-0 overflow-hidden">
            <AnalysisHistoryChart analyses={analyses} />
          </div>
        </div>
      </div>

      {analyses.length === 0 ? (
        <div className="card text-center py-12">
          <Search className="h-16 w-16 text-gray-400 dark:text-gray-500 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">У вас пока нет анализов</h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">Создайте первый анализ</p>
          <button onClick={() => setShowNewAnalysisModal(true)} className="btn-primary inline-flex items-center space-x-2">
            <Plus className="h-5 w-5" />
            <span>Создать анализ</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Все анализы ({filteredAnalyses.length})
            </h2>
            <div className="flex items-center space-x-3">
              <div className="relative w-96">
                <input
                  type="text"
                  placeholder="Название анализа"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="input-field pr-4 py-2 text-sm w-full"
                  style={{ paddingLeft: '2.5rem' }}
                />
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
              </div>
              <div className="relative" ref={regionDropdownRef}>
                <button
                  onClick={() => setShowRegionDropdown(!showRegionDropdown)}
                  className="input-field py-1.5 text-sm flex items-center justify-between overflow-hidden"
                  style={{ width: '250px', minWidth: '250px' }}
                >
                  <span className="truncate">{getTruncatedRegionText(getRegionFilterText())}</span>
                  <div className="flex items-center ml-2 flex-shrink-0">
                    {selectedRegions.length > 0 && (
                      <X className="h-4 w-4 mr-1" onClick={(e) => { e.stopPropagation(); clearRegions(); }} />
                    )}
                    <ChevronDown className="h-4 w-4" />
                  </div>
                </button>
                {showRegionDropdown && (
                  <div className="absolute right-0 mt-1 bg-white dark:bg-gray-800 border border-gray-250 dark:border-gray-700 rounded-lg shadow-lg z-50 min-w-[250px] max-h-[145px] overflow-y-auto">
                    {availableRegions.length === 0 ? (
                      <div className="px-4 py-2 text-sm text-gray-500 dark:text-gray-400">Нет доступных регионов</div>
                    ) : (
                      availableRegions.map((region) => (
                        <label
                          key={region.value}
                          className="flex items-center px-4 py-2 hover:bg-gray-100 dark:hover:bg-gray-700 cursor-pointer"
                        >
                          <input
                            type="checkbox"
                            checked={selectedRegions.includes(region.value)}
                            onChange={() => toggleRegion(region.value)}
                            className="mr-3 h-4 w-4 text-primary-600 border-gray-300 rounded focus:ring-primary-500"
                          />
                          <span className="text-sm text-gray-700 dark:text-gray-300">{region.label}</span>
                        </label>
                      ))
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>

          {paginatedAnalyses.length === 0 ? (
            <div className="card text-center py-8">
              <Filter className="h-12 w-12 text-gray-400 mx-auto mb-4" />
              <p className="text-gray-500 dark:text-gray-400">Нет анализов по заданным фильтрам</p>
            </div>
          ) : (
            paginatedAnalyses.map((analysis) => (
              <div key={analysis.id} className="card flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                <div className="flex-1">
                  <div className="flex items-center space-x-3 mb-2">
                    <span className="px-2 py-1 text-xs font-medium rounded-full bg-primary-100 text-primary-700 dark:bg-primary-900 dark:text-primary-300">
                      Ручной
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      {analysis.competitors_count} {
                        analysis.competitors_count === 1 ? 'конкурент' :
                          'конкурента'
                      }
                    </span>                  </div>
                  <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-2 flex items-center gap-2">
                    <span className="truncate max-w-md">{analysis.name || `Анализ #${analysis.id}`}</span>
                    {problemIds.includes(analysis.id) && (
                      <span
                        className="text-yellow-500 dark:text-yellow-400 shrink-0"
                        title="Цены не удаётся обновить — проверьте селекторы или некоторые сайты сейчас недоступны"
                      >
                        <AlertTriangle className="h-4 w-4" />
                      </span>
                    )}
                  </h3>
                  <div className="flex items-center space-x-4 text-sm text-gray-600 dark:text-gray-400">
                    <span className="flex items-center space-x-1">
                      <Calendar className="h-4 w-4" />
                      <span>{formatDate(analysis.created_at)}</span>
                    </span>
                    <span className="flex items-center space-x-1">
                      <Globe className="h-4 w-4" />
                      <span>{getRegionName(analysis.region)}</span>
                    </span>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  <Link to={`/analysis/${analysis.id}`} state={{ demo: isDemo }} className="btn-secondary flex items-center space-x-1">
                    <Eye className="h-4 w-4" />
                    <span>Открыть</span>
                  </Link>
                  {isDemo ? (
                    <button onClick={() => showError('Вы в деморежиме. Удаление недоступно.')} className="p-2 text-gray-400 dark:text-gray-500 cursor-not-allowed opacity-50">
                      <Trash2 className="h-5 w-5" />
                    </button>
                  ) : (
                    <button onClick={() => deleteAnalysis(analysis.id)} className="p-2 text-gray-400 dark:text-gray-500 hover:text-red-600 dark:hover:text-red-400 transition-colors">
                      <Trash2 className="h-5 w-5" />
                    </button>
                  )}
                </div>
              </div>
            ))
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-500">
                Показано {(currentPage - 1) * ITEMS_PER_PAGE + 1}-{Math.min(currentPage * ITEMS_PER_PAGE, filteredAnalyses.length)} из {filteredAnalyses.length}
              </p>
              <div className="flex items-center space-x-2">
                <button onClick={() => setCurrentPage(p => Math.max(1, p - 1))} disabled={currentPage === 1} className="btn-secondary p-2">
                  <ChevronLeft className="h-4 w-4" />
                </button>
                {Array.from({ length: Math.min(5, totalPages) }, (_, i) => {
                  let pageNum
                  if (totalPages <= 5) pageNum = i + 1
                  else if (currentPage <= 3) pageNum = i + 1
                  else if (currentPage >= totalPages - 2) pageNum = totalPages - 4 + i
                  else pageNum = currentPage - 2 + i
                  return (
                    <button
                      key={pageNum}
                      onClick={() => setCurrentPage(pageNum)}
                      className={`w-8 h-8 rounded-lg text-sm font-medium ${currentPage === pageNum ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                        }`}
                    >
                      {pageNum}
                    </button>
                  )
                })}
                <button onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))} disabled={currentPage === totalPages} className="btn-secondary p-2">
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {showNewAnalysisModal && (
        <NewAnalysisModal
          onClose={() => setShowNewAnalysisModal(false)}
          onSuccess={(analysis) => {
            setShowNewAnalysisModal(false)
            navigate(`/analysis/${analysis.id}`)
          }}
        />
      )}
    </div>
  )
}

function NewAnalysisModal({ onClose, onSuccess }) {
  const [region, setRegion] = useState('213')
  const [regionSearch, setRegionSearch] = useState('')
  const [analysisName, setAnalysisName] = useState('')
  const [userSite, setUserSite] = useState('')
  const [competitors, setCompetitors] = useState([''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [checkResults, setCheckResults] = useState({})
  const [checkingSite, setCheckingSite] = useState(null)
  const { error: showError } = useToast()


  // Получаем количество анализов пользователя для автогенерации названия
  useEffect(() => {
    const fetchAnalysesCount = async () => {
      try {
        const response = await api.get('/analysis')
        const count = response.data.analyses?.length || 0
        setAnalysisName(`Анализ #${count + 1}`)
      } catch (error) {
        console.error('Error fetching analyses count:', error)
        setAnalysisName('Анализ #1')
      }
    }
    fetchAnalysesCount()
  }, [])


  const checkSite = async (site) => {
    if (!site) return
    setCheckingSite(site)
    try {
      const res = await api.post('/analysis/check-site', { url: site })
      const data = res.data
      // Если сайт относится к исключенным, показываем только тост, но не сохраняем результат для отображения под кнопкой
      if (data.is_excluded) {
        showError(data.message || 'Сайт относится к агрегаторам/маркетплейсам/мессенджерам/поисковикам')
        // Не сохраняем результат в checkResults, чтобы текст под кнопкой не отображался
      } else {
        setCheckResults(prev => ({ ...prev, [site]: data }))
      }
    } catch (err) {
      setCheckResults(prev => ({ ...prev, [site]: { available: false, message: err.response?.data?.message || err.message } }))
    } finally {
      setCheckingSite(null)
    }
  }

  const regions = REGIONS

  const filteredRegions = regions.filter(r => r.label.toLowerCase().includes(regionSearch.toLowerCase()))

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (loading) return // защита от повторной отправки (двойного клика)
    setError('')

    const filledCompetitors = competitors.filter(c => c.trim())
    if (filledCompetitors.length === 0) {
      showError('Укажите хотя бы одного конкурента для создания анализа')
      return
    }

    // Конкурент не должен совпадать с вашим сайтом (сравниваем по домену)
    const normalizeHost = (u) => (u || '').trim().toLowerCase()
      .replace(/^https?:\/\//, '').replace(/^www\./, '').split('/')[0]
    const userHost = normalizeHost(userSite)
    if (userHost && filledCompetitors.some(c => normalizeHost(c) === userHost)) {
      showError('Сайт конкурента не должен совпадать с вашим сайтом')
      return
    }

    // Блокируем кнопку на всё время отправки, включая проверку сайтов
    setLoading(true)
    try {
      // Проверяем сайты на исключённые — параллельно, чтобы не ждать по очереди
      const sitesToCheck = []
      if (userSite) sitesToCheck.push(userSite)
      competitors.forEach(c => { if (c.trim()) sitesToCheck.push(c.trim()) })

      const checks = await Promise.allSettled(
        sitesToCheck.map(site => api.post('/analysis/check-site', { url: site }))
      )
      for (const r of checks) {
        const payload = r.status === 'fulfilled' ? r.value.data : r.reason?.response?.data
        if (payload?.is_excluded) {
          showError(payload.message || 'Сайт относится к агрегаторам/маркетплейсам/мессенджерам/поисковикам')
          return // finally сбросит loading
        }
      }

      const data = {
        type: 'manual',
        region,
        user_site: userSite,
        competitors: competitors.filter(c => c.trim()).map(domain => ({ domain: domain.trim() }))
      }
      if (analysisName && analysisName.trim()) {
        data.name = analysisName.trim()
      }
      const response = await api.post('/analysis', data)
      onSuccess(response.data.analysis)
    } catch (err) {
      setError(err.response?.data?.error || 'Ошибка при создании анализа')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white dark:bg-gray-800 rounded-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
        <div className="p-6 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white">Новый анализ</h2>
        </div>
        <form onSubmit={handleSubmit} className="p-6 space-y-6">
          {error && <div className="p-3 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-lg">{error}</div>}

          <div className="relative">
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Регион</label>

            {/* Контейнер для select */}
            <div className="relative">
              <select
                value={region}
                onChange={(e) => setRegion(e.target.value)}
                className="input-field w-full appearance-none" // appearance-none убирает стандартную стрелку
              >
                {filteredRegions.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
              </select>

              {/* Кастомная стрелка */}
              <ChevronDown className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-500 pointer-events-none" />
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Название анализа</label>
            <input
              type="text"
              value={analysisName}
              onChange={(e) => setAnalysisName(e.target.value)}
              className="input-field"
              placeholder="Оставьте пустым для автоматического названия"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ваш сайт (URL на каталог с товарами)</label>
            <div className="flex items-center space-x-2">
              <input
                type="text"
                value={userSite}
                onChange={(e) => setUserSite(e.target.value)}
                className="input-field flex-1"
                placeholder="example.ru/catalog/"
                required
              />
              <button
                type="button"
                onClick={() => checkSite(userSite)}
                disabled={!userSite || checkingSite === userSite}
                className="btn-secondary whitespace-nowrap"
              >
                {checkingSite === userSite ? 'Проверка...' : 'Проверить'}
              </button>
              {checkResults[userSite] && (
                <span className={`text-sm font-medium ${checkResults[userSite].available ? 'text-green-600' : 'text-red-600'}`}>
                  {checkResults[userSite].available ? '✅ Доступен' : `❌ ${checkResults[userSite].message || 'Нет ответа'}`}
                </span>
              )}
            </div>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Сайт конкурента (URL на каталог с товарами)</label>
            {competitors.map((comp, index) => (
              <div key={index} className="flex items-center space-x-2 mb-2">
                <input type="text" value={comp} onChange={(e) => { const updated = [...competitors]; updated[index] = e.target.value; setCompetitors(updated); }} className="input-field flex-1" placeholder={`competitor_${index + 1}.ru/catalog/`} />
                <button
                  type="button"
                  onClick={() => checkSite(comp)}
                  disabled={!comp || checkingSite === comp}
                  className="btn-secondary whitespace-nowrap"
                >
                  {checkingSite === comp ? 'Проверка...' : 'Проверить'}
                </button>
                {checkResults[comp] && (
                  <span className={`text-sm font-medium ${checkResults[comp].available ? 'text-green-600' : 'text-red-600'}`}>
                    {checkResults[comp].available ? '✅ Доступен' : `❌ ${checkResults[comp].message || 'Нет ответа'}`}
                  </span>
                )}
                {competitors.length > 1 && <button type="button" onClick={() => setCompetitors(competitors.filter((_, i) => i !== index))} className="btn-secondary p-2"><Trash2 className="h-5 w-5" /></button>}
              </div>
            ))}
            {competitors.length < 3 && <button type="button" onClick={() => setCompetitors([...competitors, ''])} className="text-sm text-primary-600">+ Добавить конкурента</button>}
          </div>

          <div className="flex justify-end space-x-4 pt-4 border-t">
            <button type="button" onClick={onClose} className="btn-secondary">Отмена</button>
            <button type="submit" disabled={loading} className="btn-primary flex items-center space-x-2">
              {loading ? <><span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></span><span>Создание...</span></> : <><span>Создать</span><ChevronRight className="h-4 w-4" /></>}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
