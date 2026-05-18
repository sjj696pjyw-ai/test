import { useState, useEffect, useMemo } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { useToast } from '../context/ToastContext'
import api from '../utils/api'
import { Plus, Calendar, Globe, Trash2, Eye, Search, Edit3, ChevronLeft, ChevronRight, Filter, TrendingUp, Users, BarChart3 } from 'lucide-react'
import { REGIONS, getRegionName } from '../utils/regions'
import { formatDate } from '../utils/export'
import { AnalysisHistoryChart, CompetitorsDistribution } from '../components/Charts'

const ITEMS_PER_PAGE = 10

const DEMO_ANALYSES = [
  {
    id: 1,
    analysis_type: 'auto',
    competitors_count: 8,
    created_at: new Date(Date.now() - 2 * 24 * 60 * 60 * 1000).toISOString(),
    region: 'Москва',
    queries: ['iPhone 15 Pro', 'Samsung Galaxy S24'],
    avg_price: 85420,
    lowest_price: 78990,
    highest_price: 99990
  },
  {
    id: 2,
    analysis_type: 'manual',
    competitors_count: 5,
    created_at: new Date(Date.now() - 5 * 24 * 60 * 60 * 1000).toISOString(),
    region: 'Санкт-Петербург',
    queries: ['Ноутбук Dell XPS'],
    avg_price: 125000,
    lowest_price: 119990,
    highest_price: 135000
  },
  {
    id: 3,
    analysis_type: 'auto',
    competitors_count: 12,
    created_at: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString(),
    region: 'Москва',
    queries: ['Sony PlayStation 5'],
    avg_price: 49990,
    lowest_price: 45990,
    highest_price: 54990
  }
]

export default function Dashboard() {
  const [analyses, setAnalyses] = useState([])
  const [loading, setLoading] = useState(true)
  const [showNewAnalysisModal, setShowNewAnalysisModal] = useState(false)
  const [currentPage, setCurrentPage] = useState(1)
  const [filterType, setFilterType] = useState('all')
  const [searchQuery, setSearchQuery] = useState('')
  const { user } = useAuth()
  const { success, error: showError } = useToast()
  const navigate = useNavigate()
  const location = useLocation()
  const isDemo = location.state?.demo === true

  useEffect(() => {
    if (isDemo) {
      setAnalyses(DEMO_ANALYSES)
      setLoading(false)
    } else {
      fetchAnalyses()
    }
  }, [isDemo])

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

  const deleteAnalysis = async (id) => {
    try {
      await api.delete(`/analysis/${id}`)
      setAnalyses(analyses.filter(a => a.id !== id))
      success('Анализ удалён')
    } catch (error) {
      showError('Ошибка при удалении')
    }
  }

  const filteredAnalyses = useMemo(() => {
    return analyses.filter(a => {
      const matchesType = filterType === 'all' || a.analysis_type === filterType
      const searchLower = searchQuery.toLowerCase()
      const matchesSearch = !searchQuery ||
        a.name?.toLowerCase().includes(searchLower)
      return matchesType && matchesSearch
    })
  }, [analyses, filterType, searchQuery])

  const totalPages = Math.ceil(filteredAnalyses.length / ITEMS_PER_PAGE)
  const paginatedAnalyses = filteredAnalyses.slice(
    (currentPage - 1) * ITEMS_PER_PAGE,
    currentPage * ITEMS_PER_PAGE
  )

  useEffect(() => {
    setCurrentPage(1)
  }, [filterType, searchQuery])

  const stats = {
    total: analyses.length,
    autoCount: analyses.filter(a => a.analysis_type === 'auto').length,
    manualCount: analyses.filter(a => a.analysis_type === 'manual').length,
    totalCompetitors: analyses.reduce((acc, a) => acc + (a.competitors_count || 0), 0)
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

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
              <div className="card flex items-center space-x-4">
                <div className="w-12 h-12 bg-primary-100 dark:bg-primary-900 rounded-lg flex items-center justify-center">
                  <BarChart3 className="h-6 w-6 text-primary-600 dark:text-primary-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Всего анализов</p>
                </div>
              </div>
              <div className="card flex items-center space-x-4">
                <div className="w-12 h-12 bg-green-100 dark:bg-green-900 rounded-lg flex items-center justify-center">
                  <Search className="h-6 w-6 text-green-600 dark:text-green-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.autoCount}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Автоматических</p>
                </div>
              </div>
              <div className="card flex items-center space-x-4">
                <div className="w-12 h-12 bg-purple-100 dark:bg-purple-900 rounded-lg flex items-center justify-center">
                  <Edit3 className="h-6 w-6 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.manualCount}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Ручных</p>
                </div>
              </div>
              <div className="card flex items-center space-x-4">
                <div className="w-12 h-12 bg-orange-100 dark:bg-orange-900 rounded-lg flex items-center justify-center">
                  <Users className="h-6 w-6 text-orange-600 dark:text-orange-400" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.totalCompetitors}</p>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Конкурентов</p>
                </div>
              </div>
            </div>

      {analyses.length > 0 && (
        <div className="flex justify-center mb-8">
          <div className="card w-full max-w-2xl">
            <h3 className="text-lg font-semibold mb-4">История анализов</h3>
            <div className="h-48">
              <AnalysisHistoryChart analyses={analyses} />
            </div>
          </div>
        </div>
      )}

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
                    placeholder="     Мои анализы"
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="input-field pl-10 pr-4 py-2 text-sm w-full"
                  />
                  <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-gray-400 pointer-events-none" />
              </div>
              <select
                value={filterType}
                onChange={(e) => setFilterType(e.target.value)}
                className="input-field py-1.5 text-sm"
              >
                <option value="all">Все типы</option>
                <option value="auto">Автоматические</option>
                <option value="manual">Ручные</option>
              </select>
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
                      {analysis.analysis_type === 'auto' ? 'Автоматический' : 'Ручной'}
                    </span>
                    <span className="text-sm text-gray-500 dark:text-gray-400">{analysis.competitors_count} конкурентов</span>
                  </div>
                  <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-2 truncate max-w-md">
                    {analysis.name || `Анализ #${analysis.id}`}
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
                  {analysis.queries && analysis.queries.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {analysis.queries.slice(0, 3).map((q, i) => (
                        <span key={i} className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded">
                          {q}
                        </span>
                      ))}
                      {analysis.queries.length > 3 && (
                        <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 rounded">
                          +{analysis.queries.length - 3}
                        </span>
                      )}
                    </div>
                  )}
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
                      className={`w-8 h-8 rounded-lg text-sm font-medium ${
                        currentPage === pageNum ? 'bg-primary-600 text-white' : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
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
  const [analysisType, setAnalysisType] = useState('auto')
  const [region, setRegion] = useState('213')
  const [regionSearch, setRegionSearch] = useState('')
  const [analysisName, setAnalysisName] = useState('')
  const [queries, setQueries] = useState('')
  const [positions, setPositions] = useState(5)
  const [resultTypes, setResultTypes] = useState(['organic'])
  const [userSite, setUserSite] = useState('')
  const [competitors, setCompetitors] = useState([''])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [showCompetitorSelection, setShowCompetitorSelection] = useState(false)
  const [foundCompetitors, setFoundCompetitors] = useState([])
  const [selectedCompetitors, setSelectedCompetitors] = useState([])
  const [analysisId, setAnalysisId] = useState(null)
  const [checkResults, setCheckResults] = useState({})
  const [checkingSite, setCheckingSite] = useState(null)
  const { error: showError } = useToast()

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

  // City prefixes for domain adaptation (city name in translit)
  const cityPrefixes = {
    '2': 'spb',           // Санкт-Петербург
    '54': 'ekb',          // Екатеринбург
    '47': 'nsk',          // Новосибирск
    '43': 'krd',          // Краснодар
    '120': 'kazan',       // Казань
    '51': 'samara',       // Самара
    '24': 'voronezh',     // Воронеж
    '35': 'nn',           // Нижний Новгород
    '39': 'rostov',       // Ростов-на-Дону
    '38': 'volgograd',    // Волгоград
    '59': 'perm',         // Пермь
    '28': 'ufa',          // Уфа
    '48': 'omsk',         // Омск
    '50': 'chelyabinsk',  // Челябинск
    '64': 'saratov',      // Саратов
    '189': 'tyumen',      // Тюмень
    '30': 'krasnoyarsk',  // Красноярск
    '66': 'izhevsk',      // Ижевск
    '75': 'stavropol',    // Ставрополь
    '44': 'sochi',        // Сочи
    '58': 'penza',        // Пенза
    '57': 'orenburg',     // Оренбург
    '192': 'kemerovo',    // Кемерово
    '69': 'tomsk',        // Томск
    '68': 'ulyanovsk',    // Ульяновск
    '22': 'khabarovsk',   // Хабаровск
    '26': 'vladivostok',  // Владивосток
    '70': 'tolyatti',     // Тольятти
    '49': 'barnaul',      // Барнаул
    '213': 'msk',         // Москва (default)
  }

  // Function to adapt domain based on city/region
  const adaptDomainForCity = (domain, regionId) => {
    // Don't adapt for Moscow (default) or if domain already has subdomain
    if (regionId === '213' || domain.includes('.')) {
      return domain
    }

    const prefix = cityPrefixes[regionId]
    if (!prefix) {
      return domain
    }

    // For domains like rus-buket.ru, return novosibirsk.rus-buket.ru
    return `${prefix}.${domain}`
  }

  const filteredRegions = regions.filter(r => r.label.toLowerCase().includes(regionSearch.toLowerCase()))

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    
    // Проверяем, не являются ли введенные сайты исключенными
    const sitesToCheck = []
    if (userSite) sitesToCheck.push(userSite)
    competitors.forEach(c => { if (c.trim()) sitesToCheck.push(c.trim()) })
    
    for (const site of sitesToCheck) {
      try {
        const res = await api.post('/analysis/check-site', { url: site })
        if (res.data.is_excluded) {
          showError(res.data.message || 'Сайт относится к агрегаторам/маркетплейсам/мессенджерам/поисковикам')
          return // Прерываем создание анализа
        }
      } catch (err) {
        // Если ошибка от сервера (например, сайт исключен), тоже прерываем
        if (err.response?.data?.is_excluded) {
          showError(err.response.data.message || 'Сайт относится к агрегаторам/маркетплейсам/мессенджерам/поисковикам')
          return
        }
        // Игнорируем другие ошибки проверки, продолжаем
      }
    }
    
    setLoading(true)
    try {
      const data = {
        type: analysisType,
        region,
        queries: queries.split('\n').filter(q => q.trim()),
        positions,
        result_types: resultTypes
      }
      if (analysisName && analysisName.trim()) {
        data.name = analysisName.trim()
      }
      if (analysisType === 'manual') {
        data.user_site = userSite
        data.competitors = competitors.filter(c => c.trim()).map(domain => ({ domain: domain.trim() }))
      } else {
        data.user_site = userSite
      }
      const response = await api.post('/analysis', data)
      if (response.data.require_selection) {
        setAnalysisId(response.data.analysis_id)
        setFoundCompetitors(response.data.found_competitors || [])
        setSelectedCompetitors([])
        setShowCompetitorSelection(true)
      } else {
        onSuccess(response.data.analysis)
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Ошибка при создании анализа')
    } finally {
      setLoading(false)
    }
  }

  const handleCompetitorSelect = (domain) => {
    if (selectedCompetitors.includes(domain)) {
      setSelectedCompetitors(selectedCompetitors.filter(d => d !== domain))
    } else if (selectedCompetitors.length < 3) {
      setSelectedCompetitors([...selectedCompetitors, domain])
    }
  }

  const handleConfirmCompetitors = async () => {
    if (selectedCompetitors.length === 0) return
    setLoading(true)
    try {
      await api.post(`/analysis/${analysisId}/select-competitors`, {
        competitors: selectedCompetitors.map(domain => ({ domain }))
      })
      setShowCompetitorSelection(false)
      onSuccess({ id: analysisId })
    } catch (err) {
      setError(err.response?.data?.error || 'Ошибка при выборе конкурентов')
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
          
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Тип анализа</label>
            <div className="grid grid-cols-2 gap-4">
              <button type="button" onClick={() => setAnalysisType('auto')} className={`p-4 border-2 rounded-lg text-left transition-colors ${analysisType === 'auto' ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30' : 'border-gray-200 dark:border-gray-600 hover:border-gray-300'}`}>
                <Search className={`h-6 w-6 mb-2 ${analysisType === 'auto' ? 'text-primary-600 dark:text-primary-400' : 'text-primary-600'}`} />
                <h4 className={`font-semibold ${analysisType === 'auto' ? 'text-primary-800 dark:text-primary-200' : ''}`}>Автоматический</h4>
                <p className={`text-sm ${analysisType === 'auto' ? 'text-primary-700 dark:text-primary-300' : 'text-gray-600 dark:text-gray-300'}`}>Поиск конкурентов</p>
              </button>
              <button type="button" onClick={() => setAnalysisType('manual')} className={`p-4 border-2 rounded-lg text-left transition-colors ${analysisType === 'manual' ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30' : 'border-gray-200 dark:border-gray-600 hover:border-gray-300'}`}>
                <Edit3 className={`h-6 w-6 mb-2 ${analysisType === 'manual' ? 'text-primary-600 dark:text-primary-400' : 'text-primary-600'}`} />
                <h4 className={`font-semibold ${analysisType === 'manual' ? 'text-primary-800 dark:text-primary-200' : ''}`}>Ручной ввод</h4>
                <p className={`text-sm ${analysisType === 'manual' ? 'text-primary-700 dark:text-primary-300' : 'text-gray-600 dark:text-gray-300'}`}>Указать сайты</p>
              </button>
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Регион</label>
            <select value={region} onChange={(e) => setRegion(e.target.value)} className="input-field">
              {filteredRegions.map(r => <option key={r.value} value={r.value}>{r.label}</option>)}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Название анализа (необязательно)</label>
            <input
              type="text"
              value={analysisName}
              onChange={(e) => setAnalysisName(e.target.value)}
              className="input-field"
              placeholder="Оставьте пустым для автоматического названия"
            />
          </div>

          {analysisType === 'auto' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ваш сайт</label>
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={userSite}
                    onChange={(e) => setUserSite(e.target.value)}
                    className="input-field flex-1"
                    placeholder="example.ru"
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
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Поисковые запросы</label>
                <textarea value={queries} onChange={(e) => setQueries(e.target.value)} className="input-field min-h-[100px]" placeholder="iphone 15&#10;samsung galaxy" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Количество позиций (1-10)</label>
                <input type="number" min="1" max="10" value={positions} onChange={(e) => setPositions(parseInt(e.target.value) || 5)} className="input-field" />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Тип выдачи</label>
                <div className="flex flex-wrap gap-3">
                  {[
                    { value: 'organic', label: 'Органическая' },
                    { value: 'cpc', label: 'Рекламная' },
                  ].map(type => (
                    <label key={type.value} className="flex items-center space-x-2 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={resultTypes.includes(type.value)}
                        onChange={(e) => {
                          if (e.target.checked) {
                            setResultTypes([...resultTypes, type.value])
                          } else {
                            setResultTypes(resultTypes.filter(t => t !== type.value))
                          }
                        }}
                        className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                      />
                      <span className="text-sm text-gray-700 dark:text-gray-300">{type.label}</span>
                    </label>
                  ))}
                </div>
              </div>
            </>
          )}

          {analysisType === 'manual' && (
            <>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Ваш сайт</label>
                <div className="flex items-center space-x-2">
                  <input 
                    type="text" 
                    value={userSite} 
                    onChange={(e) => setUserSite(e.target.value)} 
                    className="input-field flex-1" 
                    placeholder="example.ru" 
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
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Конкуренты (до 3)</label>
                {competitors.map((comp, index) => (
                  <div key={index} className="flex items-center space-x-2 mb-2">
                    <input type="text" value={comp} onChange={(e) => { const updated = [...competitors]; updated[index] = e.target.value; setCompetitors(updated); }} className="input-field flex-1" placeholder={`Конкурент ${index + 1}`} />
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
                    {competitors.length > 1 && <button type="button" onClick={() => setCompetitors(competitors.filter((_, i) => i !== index))} className="btn-secondary p-2">-</button>}
                  </div>
                ))}
                {competitors.length < 3 && <button type="button" onClick={() => setCompetitors([...competitors, ''])} className="text-sm text-primary-600">+ Добавить</button>}
              </div>
            </>
          )}

          {showCompetitorSelection ? (
            <div className="space-y-6">
              <div>
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">Найдено {foundCompetitors.length} конкурентов</h3>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">Выберите конкурентов для анализа цен. Тип выдачи указан на основе выбранных вами параметров поиска.</p>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-gray-200 dark:border-gray-700">
                      <th className="pb-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300 w-10"></th>
                      <th className="pb-3 text-left text-sm font-semibold text-gray-700 dark:text-gray-300">Сайт</th>
                      <th className="pb-3 text-center text-sm font-semibold text-gray-700 dark:text-gray-300">Позиция</th>
                      <th className="pb-3 text-right text-sm font-semibold text-gray-700 dark:text-gray-300">Тип выдачи</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-800">
                    {foundCompetitors.map((comp, index) => {
                      const displayDomain = adaptDomainForCity(comp.domain, region)
                      const types = comp.types || ['organic']
                      const hasAd = types.includes('ad') || types.includes('ads')
                      const hasOrganic = types.includes('organic')
                      const position = comp.positions ? Object.values(comp.positions)[0] : index + 1
                      const isSelected = selectedCompetitors.includes(comp.domain)
                      return (
                        <tr
                          key={index}
                          onClick={() => handleCompetitorSelect(comp.domain)}
                          className={`cursor-pointer transition-colors ${
                            isSelected ? 'bg-primary-50 dark:bg-primary-900/20' : 'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                          }`}
                        >
                          <td className="py-3 pr-2">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => {}}
                              className="rounded border-gray-300 text-primary-600 focus:ring-primary-500"
                            />
                          </td>
                          <td className="py-3">
                            <a
                              href={`https://${displayDomain}`}
                              target="_blank"
                              rel="noopener noreferrer"
                              onClick={(e) => e.stopPropagation()}
                              className="font-medium text-primary-600 dark:text-primary-400 hover:underline"
                            >
                              {displayDomain}
                            </a>
                          </td>
                          <td className="py-3 text-center">
                            <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-700 text-sm font-semibold text-gray-700 dark:text-gray-300">
                              {position}
                            </span>
                          </td>
                          <td className="py-3 text-right">
                            <div className="flex flex-wrap gap-1 justify-end">
                              {hasAd && (
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200">
                                  Платная
                                </span>
                              )}
                              {hasOrganic && (
                                <span className="inline-flex items-center px-3 py-1 rounded-full text-xs font-medium bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200">
                                  Органическая
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>

              <p className="text-sm text-gray-500 dark:text-gray-400">
                Выберите до 3 конкурентов
              </p>

              <div className="flex justify-between items-center pt-4 border-t border-gray-200 dark:border-gray-700">
                <button type="button" onClick={() => setShowCompetitorSelection(false)} className="btn-secondary">← Назад</button>
                <button
                  type="button"
                  onClick={handleConfirmCompetitors}
                  disabled={selectedCompetitors.length === 0 || loading}
                  className="btn-primary flex items-center space-x-2"
                >
                  {loading ? (
                    <><span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></span><span>Сохранение...</span></>
                  ) : (
                    <><span>Далее — сбор цен</span><ChevronRight className="h-4 w-4" /></>
                  )}
                </button>
              </div>
            </div>
          ) : (
            <div className="flex justify-end space-x-4 pt-4 border-t">
              <button type="button" onClick={onClose} className="btn-secondary">Отмена</button>
              <button type="submit" disabled={loading} className="btn-primary flex items-center space-x-2">
                {loading ? <><span className="animate-spin rounded-full h-4 w-4 border-2 border-white border-t-transparent"></span><span>Создание...</span></> : <><span>Создать</span><ChevronRight className="h-4 w-4" /></>}
              </button>
            </div>
          )}
        </form>
      </div>
    </div>
  )
}
