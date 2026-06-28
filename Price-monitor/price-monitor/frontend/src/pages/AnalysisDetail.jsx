import { useState, useEffect } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import api from '../utils/api'
import {
  ArrowLeft,
  Download,
  Link as LinkIcon,
  X,
  Check,
  Settings,
  Trash2,
  Edit3,
  Save,
  XCircle,
  RefreshCw,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  HelpCircle,
  Store,
  Plus,
} from 'lucide-react'
import { getRegionName } from '../utils/regions'
import { exportToExcel, exportToCSV, formatPrice, formatDate } from '../utils/export'
import { PriceDynamicsChart } from '../components/PriceDynamicsChart'
import AddCatalogModal from '../components/AddCatalogModal'
import { useToast } from '../context/ToastContext'

const productPlural = (n) => {
  const m10 = n % 10,
    m100 = n % 100
  if (m10 === 1 && m100 !== 11) return 'товар'
  if (m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20)) return 'товара'
  return 'товаров'
}

const cleanUrl = (u) => (u || '').replace(/^https?:\/\//, '').replace(/\/+$/, '')

// Частые двухуровневые публичные суффиксы (site.msk.ru, shop.co.uk).
const MULTI_SUFFIXES = new Set([
  'msk.ru', 'spb.ru', 'com.ru', 'net.ru', 'org.ru', 'edu.ru', 'gov.ru',
  'co.uk', 'org.uk', 'com.ua', 'co.il', 'com.br', 'com.tr', 'com.kz',
  'com.by', 'co.kz',
])

// Основной (регистрируемый) домен: novosibirsk.rus-buket.ru → rus-buket.ru.
const baseDomain = (urlOrHost) => {
  let h = (urlOrHost || '')
    .trim()
    .toLowerCase()
    .replace(/^https?:\/\//, '')
    .replace(/^www\./, '')
    .split('/')[0]
    .replace(/^\.+|\.+$/g, '')
  if (!h) return ''
  const p = h.split('.')
  if (p.length <= 2) return h
  const last2 = p.slice(-2).join('.')
  return MULTI_SUFFIXES.has(last2) ? p.slice(-3).join('.') : last2
}

const withScheme = (u) => (!u ? null : /^https?:\/\//.test(u) ? u : `https://${u}`)

// Название товара: ссылка на карточку, если url есть, иначе обычный текст.
const ProductName = ({ name, url, className = '' }) => {
  const text = name || 'N/A'
  if (url) {
    return (
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        title={text}
        className={`hover:underline hover:text-primary-600 dark:hover:text-primary-400 ${className}`}
      >
        {text}
      </a>
    )
  }
  return <span className={className}>{text}</span>
}

const DEMO_DATA = {
  2: {
    id: 2,
    analysis_type: 'manual',
    region: '2',
    created_at: '2026-05-30T09:45:00.000Z',
    competitors: [
      {
        id: 104,
        domain: 'dns-shop.ru',
        is_user_site: false,
        title_selector: '.catalog-product__name',
        price_selector: '.product-price__current',
        last_price_update: new Date(Date.now() - 86400000).toISOString(),
        products: [
          { id: 210, name: 'Ноутбук Dell XPS 13 9310', price: 119990, currency: 'RUB' },
          { id: 211, name: 'Ноутбук Dell XPS 15 9520', price: 159990, currency: 'RUB' },
          { id: 212, name: 'Ноутбук Dell XPS 17 9720', price: 189990, currency: 'RUB' },
        ],
      },
      {
        id: 105,
        domain: 'eldorado.ru',
        is_user_site: false,
        title_selector: '.product__title',
        price_selector: '.product__price',
        last_price_update: new Date(Date.now() - 86400000).toISOString(),
        products: [
          { id: 213, name: 'Ноутбук Dell XPS 13 Plus 9320', price: 129990, currency: 'RUB' },
          { id: 214, name: 'Ноутбук Dell XPS 15 9530', price: 169990, currency: 'RUB' },
        ],
      },
      {
        id: 106,
        domain: 'myshop.ru',
        is_user_site: true,
        title_selector: '.title',
        price_selector: '.price',
        last_price_update: new Date(Date.now() - 86400000).toISOString(),
        products: [
          { id: 215, name: 'Ноутбук Dell XPS 13', price: 124990, currency: 'RUB' },
          { id: 216, name: 'Ноутбук Dell XPS 15', price: 164990, currency: 'RUB' },
          { id: 217, name: 'Ноутбук Dell XPS 17', price: 199990, currency: 'RUB' },
        ],
      },
    ],
    product_links: [
      { user_product_id: 215, competitor_product_id: 210 },
      { user_product_id: 216, competitor_product_id: 211 },
      { user_product_id: 217, competitor_product_id: 212 },

      { user_product_id: 215, competitor_product_id: 213 },
    ],
  },
}

function normalizeDemoAnalysis(raw) {
  const productById = {}
  ;(raw.competitors || []).forEach((c) =>
    (c.products || []).forEach((p) => {
      productById[p.id] = p
    })
  )
  const product_links = (raw.product_links || []).map((l, i) => {
    const up = productById[l.user_product_id] || null
    const cp = productById[l.competitor_product_id] || null
    const price_difference =
      up && cp && up.price != null && cp.price != null ? up.price - cp.price : null
    return { id: i + 1, user_product: up, competitor_product: cp, price_difference }
  })
  return { ...raw, product_links }
}

export default function AnalysisDetail() {
  const { id } = useParams()
  const location = useLocation()
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('report')
  const [linkingMode, setLinkingMode] = useState(null)
  const [selectedProduct, setSelectedProduct] = useState(null)

  const [selectedCompetitorProducts, setSelectedCompetitorProducts] = useState({})
  const [isEditingName, setIsEditingName] = useState(false)
  const [editingName, setEditingName] = useState('')
  const [isUpdatingPrices, setIsUpdatingPrices] = useState(false)
  const [priceDynamicsData, setPriceDynamicsData] = useState(null)
  const [userProductsPage, setUserProductsPage] = useState(0)
  const [showHowItWorksModal, setShowHowItWorksModal] = useState(false)
  const { error: showError, success } = useToast()
  const isDemo = location.state?.demo === true
  const USER_PRODUCTS_PER_PAGE = 5
  const [userProductSearch, setUserProductSearch] = useState('')
  const [competitorProductSearch, setCompetitorProductSearch] = useState({})

  const [reportProductFilter, setReportProductFilter] = useState(null)
  const [addCatalogTarget, setAddCatalogTarget] = useState(null)
  const [expandedCatalogs, setExpandedCatalogs] = useState({})

  useEffect(() => {
    fetchAnalysis()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id])

  useEffect(() => {
    if (analysis && analysis.product_links && analysis.product_links.length > 0) {
      fetchPriceDynamics()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [analysis])

  const fetchAnalysis = async () => {
    if (isDemo && DEMO_DATA[id]) {
      setAnalysis(normalizeDemoAnalysis(DEMO_DATA[id]))
      setLoading(false)
      return
    }
    try {
      const response = await api.get(`/analysis/${id}`)
      setAnalysis(response.data.analysis)
    } catch (error) {
      console.error('Error fetching analysis:', error)
    } finally {
      setLoading(false)
    }
  }

  const handleUpdatePrices = async (competitorId = null) => {
    if (isDemo) {
      showError('Обновление цен недоступно в демо-режиме')
      return
    }

    setIsUpdatingPrices(true)
    try {
      let response
      if (competitorId) {
        response = await api.post(`/analysis/competitor/${competitorId}/update-prices`)
      } else {
        response = await api.post(`/analysis/${id}/update-prices`)
      }

      const result = response.data.result

      if (response.status === 200 || response.status === 201) {
        await fetchAnalysis()

        if (competitorId) {
          success('Цены успешно обновлены')
        } else {
          if (result.overall_status === 'success') {
            success('Цены успешно обновлены')
          } else if (result.overall_status === 'rate_limited') {
            showError(
              result.rate_limited_message ||
                'Слишком частые запросы. Обновление цен доступно раз в 3 минуты.'
            )
          } else if (result.overall_status === 'partial') {
            showError(
              `По некоторым конкурентам не удалось обновить цену. Обновлено: ${result.success_count}, частично: ${result.partial_count}, ошибок: ${result.error_count}`
            )
          } else if (result.overall_status === 'error') {
            showError(`Не удалось обновить цены. Ошибок: ${result.error_count}`)
          }
        }
      } else if (response.status === 429) {
        showError(response.data.message || 'Слишком частые запросы. Попробуйте через 3 минуты.')
      } else {
        showError(response.data.message || 'Ошибка обновления цен')
      }
    } catch (error) {
      console.error('Error updating prices:', error)
      if (error.response?.status === 429) {
        showError(
          error.response.data?.message || 'Слишком частые запросы. Попробуйте через 3 минуты.'
        )
      } else {
        showError('Ошибка обновления цен')
      }
    } finally {
      setIsUpdatingPrices(false)
    }
  }

  const fetchPriceDynamics = async () => {
    if (!analysis?.product_links || analysis.product_links.length === 0) {
      setPriceDynamicsData(null)
      return
    }

    if (isDemo) {
      const compByProduct = {}
      ;(analysis.competitors || []).forEach((c) =>
        (c.products || []).forEach((p) => {
          compByProduct[p.id] = c
        })
      )
      const d = (n) => new Date(Date.now() - n * 86400000).toISOString().split('T')[0]
      setPriceDynamicsData(
        (analysis.product_links || []).map((link) => {
          const cp = link.competitor_product
          const up = link.user_product
          const base = cp?.price ?? 0
          return {
            product_name: up?.name,
            user_product_id: up?.id,
            user_site: true,
            competitor_name: cp?.name,
            competitor_domain: compByProduct[cp?.id]?.domain || '',
            product_url: null,
            data_points: [
              { date: d(7), user_price: up?.price, competitor_price: base - 3000 },
              { date: d(3), user_price: up?.price, competitor_price: base - 1500 },
              { date: d(0), user_price: up?.price, competitor_price: base },
            ],
          }
        })
      )
      return
    }

    try {
      const response = await api.get(`/analysis/${id}/price-dynamics`)
      setPriceDynamicsData(response.data.dynamics)
    } catch (error) {
      console.error('Error fetching price dynamics:', error)
      setPriceDynamicsData(null)
    }
  }

  const handleUpdateName = async () => {
    if (!editingName.trim()) {
      showError('Название не может быть пустым')
      return
    }
    try {
      await api.put(`/analysis/${id}/name`, { name: editingName.trim() })
      setAnalysis((prev) => ({ ...prev, name: editingName.trim() }))
      setIsEditingName(false)
      success('Название анализа обновлено')
    } catch (error) {
      console.error('Error updating analysis name:', error)
      showError('Ошибка при обновлении названия')
    }
  }

  const startEditingName = () => {
    setEditingName(analysis.name || `Анализ #${analysis.id}`)
    setIsEditingName(true)
  }

  const cancelEditingName = () => {
    setIsEditingName(false)
    setEditingName('')
  }

  const handleExportExcel = () => {
    if (isDemo) {
      showError('Экспорт недоступен в демо-режиме')
      return
    }
    if (!analysis?.product_links?.length) {
      showError('Нет данных для экспорта. Сначала свяжите товары.')
      return
    }

    const data = analysis.product_links.map((link) => ({
      'Товар конкурента': link.competitor_product?.name || 'N/A',
      'Ваш товар': link.user_product?.name || 'N/A',
      'Ваша цена': link.user_product?.price || 'N/A',
      'Цена конкурента': link.competitor_product?.price || 'N/A',
      'Разница (₽)':
        link.price_difference !== null
          ? `${link.price_difference >= 0 ? '+' : '-'}${Math.abs(link.price_difference)}`
          : 'N/A',
    }))

    exportToExcel(data, `analysis_${id}_${Date.now()}`)
  }

  const handleExportCSV = () => {
    if (isDemo) {
      showError('Экспорт недоступен в демо-режиме')
      return
    }
    if (!analysis?.product_links?.length) {
      showError('Нет данных для экспорта. Сначала свяжите товары.')
      return
    }

    const data = analysis.product_links.map((link) => ({
      'Товар конкурента': link.competitor_product?.name || 'N/A',
      'Ваш товар': link.user_product?.name || 'N/A',
      'Ваша цена': link.user_product?.price || 'N/A',
      'Цена конкурента': link.competitor_product?.price || 'N/A',
      'Разница (₽)':
        link.price_difference !== null
          ? `${link.price_difference >= 0 ? '+' : '-'}${Math.abs(link.price_difference)}`
          : 'N/A',
    }))

    exportToCSV(data, `analysis_${id}_${Date.now()}`)
  }

  const unlinkProducts = async (linkId) => {
    if (isDemo) {
      setAnalysis((prev) => ({
        ...prev,
        product_links: prev.product_links.filter((link) => link.id !== linkId),
      }))
      return
    }

    try {
      await api.delete(`/analysis/unlink/${linkId}`)
      await fetchAnalysis()
    } catch (error) {
      console.error('Error unlinking products:', error)

      setAnalysis((prev) => ({
        ...prev,
        product_links: prev.product_links.filter((link) => link.id !== linkId),
      }))
    }
  }

  const handleSelectCompetitorProductClick = (competitorId, productId) => {
    setSelectedCompetitorProducts((prev) => {
      if (prev[competitorId] === productId) {
        const next = { ...prev }
        delete next[competitorId]
        return next
      }

      return { ...prev, [competitorId]: productId }
    })
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const handleLinkAllSelected = async () => {
    const competitorProductIds = Object.values(selectedCompetitorProducts)
    if (!selectedProduct || competitorProductIds.length === 0) {
      showError('Выберите товары для связывания')
      return
    }
    try {
      await Promise.all(
        competitorProductIds.map((competitorProductId) =>
          api.post('/analysis/link', {
            analysis_id: parseInt(id),
            user_product_id: selectedProduct.id,
            competitor_product_id: competitorProductId,
          })
        )
      )
      await fetchAnalysis()
      setSelectedProduct(null)
      setSelectedCompetitorProducts({})
      setUserProductSearch('')
      setCompetitorProductSearch({})

      success(
        competitorProductIds.length === 1
          ? 'Товары успешно связаны'
          : `Товар связан с ${competitorProductIds.length} конкурентами`
      )
    } catch (error) {
      console.error('Error linking products:', error)
      showError('Ошибка при связывании товаров')
    }
  }

  const getUserProductsPage = () => {
    let products = userCompetitor?.products || []

    if (userProductSearch.trim()) {
      products = products.filter((p) =>
        p.name.toLowerCase().includes(userProductSearch.toLowerCase())
      )
    }
    const totalPages = Math.ceil(products.length / USER_PRODUCTS_PER_PAGE)
    const currentPage = Math.min(userProductsPage, totalPages - 1)
    const start = currentPage * USER_PRODUCTS_PER_PAGE
    const end = start + USER_PRODUCTS_PER_PAGE
    return {
      products: products.slice(start, end),
      currentPage,
      totalPages,
    }
  }

  const handleUserProductPageChange = (newPage) => {
    const products = userCompetitor?.products || []
    const totalPages = Math.ceil(products.length / USER_PRODUCTS_PER_PAGE)
    setUserProductsPage(Math.max(0, Math.min(newPage, totalPages - 1)))
  }

  if (!analysis) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
          Анализ не найден
        </h2>
        <Link to="/dashboard" className="btn-primary">
          Вернуться к списку
        </Link>
      </div>
    )
  }

  const userCompetitor = analysis.competitors?.find((c) => c.is_user_site)
  const competitorList = analysis.competitors?.filter((c) => !c.is_user_site) || []

  const productToCompetitor = {}
  competitorList.forEach((c) =>
    (c.products || []).forEach((p) => {
      productToCompetitor[p.id] = c
    })
  )

  const formatPriceInt = (price) =>
    price == null
      ? 'N/A'
      : new Intl.NumberFormat('ru-RU', {
          style: 'currency',
          currency: 'RUB',
          maximumFractionDigits: 0,
        }).format(price)

  // Список товаров конкурента/моего сайта, сгруппированный по каталогам:
  // каждый каталог — разворачиваемая сущность с кликабельным названием-ссылкой.
  const renderCatalogGroups = (entity, priceClass) => {
    const groups =
      entity.catalogs && entity.catalogs.length
        ? entity.catalogs
        : [{ id: 'all', name: null, url: entity.domain, products: entity.products || [] }]
    return (
      <div className="space-y-2">
        {groups.map((cat) => {
          const items = cat.products || []
          const key = `disp:${entity.id}:${cat.id}`
          const open = expandedCatalogs[key] ?? groups.length === 1
          const toggle = () => setExpandedCatalogs((prev) => ({ ...prev, [key]: !open }))
          const catUrl = withScheme(cat.url)
          const label = cat.name || cleanUrl(cat.url) || 'Каталог'
          return (
            <div
              key={cat.id}
              className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden"
            >
              <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800/60">
                <div className="flex items-center gap-2 min-w-0">
                  <button
                    onClick={toggle}
                    className="p-0.5 text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-200 shrink-0"
                    aria-label={open ? 'Свернуть' : 'Развернуть'}
                  >
                    {open ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                  </button>
                  {catUrl ? (
                    <a
                      href={catUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 hover:underline truncate inline-flex items-center gap-1"
                      title={label}
                    >
                      <span className="truncate">{label}</span>
                      <ExternalLink className="h-3 w-3 shrink-0" />
                    </a>
                  ) : (
                    <button
                      onClick={toggle}
                      className="text-sm font-medium text-gray-800 dark:text-gray-200 truncate"
                    >
                      {label}
                    </button>
                  )}
                </div>
                <button
                  onClick={toggle}
                  className="text-xs text-gray-500 dark:text-gray-400 shrink-0 ml-3"
                >
                  {items.length} {productPlural(items.length)}
                </button>
              </div>
              {open && (
                <div className="space-y-2 p-2 max-h-96 overflow-y-auto">
                  {items.length === 0 ? (
                    <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-3">
                      Нет товаров
                    </p>
                  ) : (
                    items.map((product) => (
                      <div
                        key={product.id}
                        className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border-b border-gray-200 dark:border-gray-700"
                      >
                        <p className="font-medium text-gray-900 dark:text-gray-100">
                          <ProductName name={product.name} url={product.url} />
                        </p>
                        <div className="flex items-center space-x-4 mt-1">
                          <p className={priceClass}>{formatPrice(product.price)}</p>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>
    )
  }

  const reportLinks = analysis.product_links || []

  const reportGroups = []
  const reportGroupIndex = {}
  reportLinks.forEach((link) => {
    const uid = link.user_product?.id ?? `link_${link.id}`
    if (reportGroupIndex[uid] === undefined) {
      reportGroupIndex[uid] = reportGroups.length
      reportGroups.push({
        userProductId: link.user_product?.id,
        userName: link.user_product?.name,
        userUrl: link.user_product?.url,
        userPrice: link.user_product?.price,
        links: [],
      })
    }
    reportGroups[reportGroupIndex[uid]].links.push(link)
  })

  const linkedUserProductIds = new Set(
    (analysis.product_links || []).map((link) => link.user_product?.id).filter(Boolean)
  )
  const linkedCompetitorProductIds = new Set(
    (analysis.product_links || []).map((link) => link.competitor_product?.id).filter(Boolean)
  )

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <Link
          to="/dashboard"
          state={{ demo: isDemo }}
          className="flex items-center text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-4"
        >
          <ArrowLeft className="h-4 w-4 mr-1" />
          Назад к списку
        </Link>
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
          <div>
            {isEditingName ? (
              <div className="flex items-center space-x-2 mb-2">
                <input
                  type="text"
                  value={editingName}
                  onChange={(e) => setEditingName(e.target.value)}
                  className="input-field py-1 px-2 text-lg font-bold"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleUpdateName()
                    if (e.key === 'Escape') cancelEditingName()
                  }}
                />
                <button
                  onClick={handleUpdateName}
                  className="p-1.5 text-green-600 hover:bg-green-100 dark:hover:bg-green-900/30 rounded transition-colors"
                >
                  <Save className="h-5 w-5" />
                </button>
                <button
                  onClick={cancelEditingName}
                  className="p-1.5 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors"
                >
                  <XCircle className="h-5 w-5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2 mb-2">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {analysis.name || `Анализ #${analysis.id}`}
                </h1>
                {!isDemo && (
                  <button
                    onClick={startEditingName}
                    className="p-1.5 text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors"
                  >
                    <Edit3 className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
            <p className="text-gray-600 dark:text-gray-400">
              {formatDate(analysis.created_at)}{' '}
              {new Date(analysis.created_at).toLocaleTimeString('ru-RU', {
                hour: '2-digit',
                minute: '2-digit',
              })}{' '}
              (UTC) • Регион: {getRegionName(analysis.region)}
            </p>

          </div>
          <div className="flex items-center space-x-2">
            <button
              onClick={handleExportExcel}
              className={`btn-secondary flex items-center space-x-2 ${isDemo ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Download className="h-4 w-4" />
              <span>Excel</span>
            </button>
            <button
              onClick={handleExportCSV}
              className={`btn-secondary flex items-center space-x-2 ${isDemo ? 'opacity-50 cursor-not-allowed' : ''}`}
            >
              <Download className="h-4 w-4" />
              <span>CSV</span>
            </button>
          </div>
        </div>
      </div>

      <div className="border-b border-gray-200 mb-6">
        <nav className="flex space-x-8">
          <button
            onClick={() => setActiveTab('report')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'report'
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600'
            }`}
          >
            Отчёт
          </button>
          <button
            onClick={() => setActiveTab('products')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'products'
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600'
            }`}
          >
            Ваши товары ({userCompetitor?.products?.length || 0})
          </button>
          <button
            onClick={() => setActiveTab('competitors')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'competitors'
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600'
            }`}
          >
            Конкуренты ({competitorList.length})
          </button>
          <button
            onClick={() => setActiveTab('linking')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${
              activeTab === 'linking'
                ? 'border-primary-500 text-primary-600 dark:text-primary-400'
                : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600'
            }`}
          >
            Связывание ({analysis.product_links?.length || 0})
          </button>
        </nav>
      </div>

      {activeTab === 'report' && (
        <div className="space-y-6">
          {analysis.product_links && analysis.product_links.length > 0 && (
            <div className="card flex justify-center">
              <div className="w-full max-w-full">
                {priceDynamicsData && priceDynamicsData.length > 0 ? (
                  <PriceDynamicsChart
                    title="График динамики цен"
                    data={priceDynamicsData}
                    selectedUserProductId={reportProductFilter}
                    onFilterChange={setReportProductFilter}
                  />
                ) : (
                  <>
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                        График динамики цен
                      </h3>
                    </div>
                    <div className="text-center py-8">
                      <p className="text-gray-500 dark:text-gray-400">
                        Нет данных для построения графика
                      </p>
                      <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
                        График появится автоматически, когда у вас и конкурентов будут товары с
                        историей цен
                      </p>
                    </div>
                  </>
                )}
              </div>
            </div>
          )}

          <div className="card">
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
              Сводный отчёт
            </h3>

            {!analysis.product_links || analysis.product_links.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-gray-500 dark:text-gray-400 mb-4">Нет данных для отображения</p>
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  Сначала добавьте товары своего сайта через{' '}
                  <button
                    onClick={() => setActiveTab('products')}
                    className="text-primary-600 dark:text-primary-400 hover:underline font-medium"
                  >
                    вкладку «Ваши товары»
                  </button>{' '}
                  (настройте селекторы и соберите товары), затем{' '}
                  <button
                    onClick={() => setActiveTab('competitors')}
                    className="text-primary-600 dark:text-primary-400 hover:underline font-medium"
                  >
                    добавьте товары конкурентов
                  </button>{' '}
                  и после свяжите через{' '}
                  <button
                    onClick={() => setActiveTab('linking')}
                    className="text-primary-600 dark:text-primary-400 hover:underline font-medium"
                  >
                    раздел «Связывание»
                  </button>
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                        Ваш товар
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                        Ваша цена
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                        Товар конкурента
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                        Цена конкурента
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                        Сайт конкурента
                      </th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">
                        Разница
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {reportGroups.flatMap((group) => {
                      const highlighted =
                        reportProductFilter && group.userProductId === reportProductFilter
                      const rowBg = highlighted
                        ? 'bg-primary-50 dark:bg-primary-900/30'
                        : 'hover:bg-gray-50 dark:hover:bg-gray-800'
                      return group.links.map((link, i) => {
                        const partner = productToCompetitor[link.competitor_product?.id]
                        const partnerDomain = partner?.domain?.replace(/^https?:\/\//, '')
                        const partnerHref =
                          link.competitor_product?.url ||
                          (partnerDomain ? `https://${partnerDomain}` : null)
                        return (
                          <tr
                            key={link.id}
                            className={`${rowBg} border-b border-gray-200 dark:border-gray-700`}
                          >
                            {i === 0 && (
                              <>
                                <td
                                  rowSpan={group.links.length}
                                  className={`px-4 py-3 text-sm text-gray-900 dark:text-gray-100 align-middle border-r border-gray-200 dark:border-gray-700 ${highlighted ? 'font-semibold' : ''}`}
                                >
                                  <ProductName name={group.userName} url={group.userUrl} />
                                </td>
                                <td
                                  rowSpan={group.links.length}
                                  className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100 align-middle border-r border-gray-200 dark:border-gray-700"
                                >
                                  {formatPriceInt(group.userPrice)}
                                </td>
                              </>
                            )}
                            <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                              <ProductName name={link.competitor_product?.name} url={link.competitor_product?.url} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                              {formatPriceInt(link.competitor_product?.price)}
                            </td>
                            <td className="px-4 py-3 text-sm">
                              {partnerHref ? (
                                <a
                                  href={partnerHref}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary-600 dark:text-primary-400 hover:underline inline-flex items-center gap-1"
                                >
                                  <span className="truncate max-w-[180px]">
                                    {partnerDomain || 'Перейти'}
                                  </span>
                                  <ExternalLink className="h-3 w-3 shrink-0" />
                                </a>
                              ) : (
                                <span className="text-gray-400 dark:text-gray-500">—</span>
                              )}
                            </td>
                            <td
                              className={`px-4 py-3 text-sm font-medium ${
                                link.price_difference > 0
                                  ? 'text-red-600 dark:text-red-400'
                                  : link.price_difference < 0
                                    ? 'text-green-600 dark:text-green-400'
                                    : 'text-gray-900 dark:text-gray-100'
                              }`}
                            >
                              {link.price_difference !== null
                                ? `${link.price_difference > 0 ? '+' : link.price_difference < 0 ? '-' : ''}${formatPriceInt(Math.abs(link.price_difference))}`
                                : 'N/A'}
                            </td>
                          </tr>
                        )
                      })
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {reportLinks.length > 0 && (
            <div className="grid md:grid-cols-3 gap-4">
              <div className="card text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400">Всего позиций</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">
                  {reportLinks.length}
                </p>
              </div>
              <div className="card text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400">Выше ценой</p>
                <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {reportLinks.filter((l) => l.price_difference > 0).length}
                </p>
              </div>
              <div className="card text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400">Ниже ценой</p>
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {reportLinks.filter((l) => l.price_difference < 0).length}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'products' && (
        <div className="space-y-6">
          {userCompetitor && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center space-x-4">
                  <span className="w-8 h-8 bg-primary-100 dark:bg-primary-900 text-primary-600 dark:text-primary-400 rounded-full flex items-center justify-center font-semibold shrink-0">
                    <Store className="h-4 w-4" />
                  </span>
                  <div>
                    {baseDomain(userCompetitor.domain || analysis.user_site) ? (
                      <a
                        href={`https://${baseDomain(userCompetitor.domain || analysis.user_site)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300 hover:underline"
                      >
                        {baseDomain(userCompetitor.domain || analysis.user_site)}
                      </a>
                    ) : (
                      <span className="font-medium text-gray-900 dark:text-white">Ваш сайт</span>
                    )}
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      {userCompetitor.products?.length || 0}{' '}
                      {productPlural(userCompetitor.products?.length || 0)}
                      {userCompetitor.last_price_update && (
                        <span className="ml-2">
                          • Цены актуальны на{' '}
                          {new Date(userCompetitor.last_price_update).toLocaleDateString('ru-RU', {
                            day: 'numeric',
                            month: 'long',
                            year: 'numeric',
                          })}{' '}
                          {new Date(userCompetitor.last_price_update).toLocaleTimeString('ru-RU', {
                            hour: '2-digit',
                            minute: '2-digit',
                          })}{' '}
                          (UTC)
                        </span>
                      )}
                    </p>
                  </div>
                </div>
                <div className="flex items-center space-x-2">
                  {!isDemo && (
                    <button
                      onClick={() => setAddCatalogTarget(userCompetitor)}
                      className="btn-secondary text-sm flex items-center space-x-2"
                    >
                      <Plus className="h-4 w-4" />
                      <span>Добавить товары</span>
                    </button>
                  )}
                  {userCompetitor.products?.length > 0 &&
                    (isDemo ? (
                      <button
                        onClick={() => showError('Настройка селекторов недоступна в демо-режиме')}
                        className="btn-secondary text-sm flex items-center space-x-2"
                      >
                        <Settings className="h-4 w-4" />
                        <span>Настроить</span>
                      </button>
                    ) : (
                      <Link
                        to={`/analysis/${id}/competitor/${userCompetitor.id}/selectors`}
                        className="btn-secondary text-sm flex items-center space-x-2"
                      >
                        <Settings className="h-4 w-4" />
                        <span>Настроить</span>
                      </Link>
                    ))}
                  {userCompetitor.products?.length > 0 && (
                    <button
                      onClick={() => handleUpdatePrices(userCompetitor.id)}
                      disabled={isUpdatingPrices}
                      className="btn-secondary text-sm flex items-center space-x-2"
                    >
                      <RefreshCw className={`h-4 w-4 ${isUpdatingPrices ? 'animate-spin' : ''}`} />
                      <span>Обновить</span>
                    </button>
                  )}
                </div>
              </div>
              {userCompetitor.products?.length > 0 ? (
                renderCatalogGroups(
                  userCompetitor,
                  'text-primary-600 dark:text-primary-400 font-semibold'
                )
              ) : (
                <div className="space-y-4">
                  <p className="text-gray-500 dark:text-gray-400">Нет товаров</p>
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Настройте селекторы для вашего сайта и соберите товары
                  </p>
                  {userCompetitor && (
                    <Link
                      to={`/analysis/${id}/competitor/${userCompetitor.id}/selectors`}
                      className="btn-primary text-sm inline-flex items-center space-x-1"
                    >
                      <Settings className="h-4 w-4" />
                      <span>Настроить селекторы и собрать товары</span>
                    </Link>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'linking' && (
        <div className="space-y-6">
          <div className="card">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Связывание товаров
                </h3>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  Свяжите ваши товары с товарами конкурентов для формирования отчёта
                </p>
              </div>
              {linkingMode ? (
                <div className="flex items-center space-x-2 mb-8">
                  <button
                    onClick={handleLinkAllSelected}
                    className="btn-primary flex items-center space-x-2"
                  >
                    <Check className="h-4 w-4" />
                    <span>Связать</span>
                  </button>
                  <button
                    onClick={() => setShowHowItWorksModal(true)}
                    className="btn-secondary flex items-center space-x-2"
                  >
                    <HelpCircle className="h-5 w-5" strokeWidth={2.5} />
                    <span>Как это работает</span>
                  </button>
                  <button
                    onClick={() => {
                      setLinkingMode(null)
                      setSelectedProduct(null)
                      setSelectedCompetitorProducts({})
                      setUserProductSearch('')
                      setCompetitorProductSearch({})
                    }}
                    className="btn-secondary flex items-center space-x-2"
                  >
                    <X className="h-4 w-4" />
                    <span>Закрыть</span>
                  </button>
                </div>
              ) : isDemo ? (
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  Связывание товаров недоступно в демо-режиме
                </span>
              ) : (
                <button
                  onClick={() => {
                    const hasUser = (userCompetitor?.products?.length || 0) > 0
                    const hasCompetitor = competitorList.some((c) => (c.products?.length || 0) > 0)
                    if (!hasUser || !hasCompetitor) {
                      showError(
                        'Сначала настройте селекторы и соберите товары — по вашему сайту и хотя бы одному конкуренту'
                      )
                      return
                    }
                    setLinkingMode('user')
                  }}
                  className="btn-primary flex items-center space-x-2"
                >
                  <LinkIcon className="h-4 w-4" />
                  <span>Связать товары</span>
                </button>
              )}
            </div>

            {linkingMode && (
              <div className="mb-6 space-y-6">
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <h5 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Ваши товары</h5>
                  <div className="mb-3">
                    <input
                      type="text"
                      placeholder="Поиск по названию товара..."
                      value={userProductSearch}
                      onChange={(e) => setUserProductSearch(e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
                    />
                  </div>
                  <div className="space-y-2">
                    {getUserProductsPage().products.length === 0 && (
                      <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                        {userProductSearch.trim() ? 'Товары не найдены' : 'Нет товаров'}
                      </p>
                    )}
                    {getUserProductsPage().products.map((product) => {
                      const isLinked = linkedUserProductIds.has(product.id)
                      return (
                        <button
                          key={product.id}
                          onClick={() => !isLinked && setSelectedProduct(product)}
                          disabled={isLinked}
                          className={`w-full p-2 text-left rounded border transition-all flex items-center justify-between ${
                            isLinked
                              ? 'border-green-500 bg-green-50 dark:bg-green-900/20 cursor-not-allowed opacity-70'
                              : selectedProduct?.id === product.id
                                ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                                : 'border-gray-200 bg-white hover:border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-gray-600'
                          }`}
                        >
                          <p className="text-sm font-medium truncate text-gray-900 dark:text-gray-100">
                            <ProductName name={product.name} url={product.url} />
                          </p>
                          <span className="flex items-center gap-2 shrink-0">
                            {isLinked && (
                              <span className="text-xs text-green-600 dark:text-green-400 font-medium flex items-center gap-1">
                                <Check className="h-3 w-3" />
                                Связан
                              </span>
                            )}
                            <span className="text-xs text-primary-600 dark:text-primary-400 font-semibold">
                              {formatPrice(product.price)}
                            </span>
                          </span>
                        </button>
                      )
                    })}
                  </div>
                  {getUserProductsPage().totalPages > 1 && (
                    <div className="flex items-center gap-2 mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
                      <span className="text-sm text-gray-600 dark:text-gray-400">
                        Страница {getUserProductsPage().currentPage + 1} из{' '}
                        {getUserProductsPage().totalPages}
                      </span>
                      <button
                        onClick={() =>
                          handleUserProductPageChange(getUserProductsPage().currentPage - 1)
                        }
                        disabled={getUserProductsPage().currentPage === 0}
                        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronLeft className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() =>
                          handleUserProductPageChange(getUserProductsPage().currentPage + 1)
                        }
                        disabled={
                          getUserProductsPage().currentPage >= getUserProductsPage().totalPages - 1
                        }
                        className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed"
                      >
                        <ChevronRight className="h-4 w-4" />
                      </button>
                    </div>
                  )}
                </div>
                <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                  <h5 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
                    Товары конкурентов
                  </h5>
                  <div className="space-y-4">
                    {competitorList.slice(0, 3).map(
                      (competitor) =>
                        !competitor.is_user_site &&
                        competitor.products?.length > 0 && (
                          <div
                            key={competitor.id}
                            className="border border-gray-200 dark:border-gray-700 rounded-lg p-3"
                          >
                            <h6 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2 flex items-center justify-between">
                              <span>{competitor.domain}</span>
                              <span className="text-xs text-gray-500 dark:text-gray-400">
                                {competitor.products.length}{' '}
                                {competitor.products.length === 1 ? 'товар' : 'товаров'}
                              </span>
                            </h6>
                            <div className="mb-2">
                              <input
                                type="text"
                                placeholder={`Поиск по названию товара...`}
                                value={competitorProductSearch[competitor.id] || ''}
                                onChange={(e) =>
                                  setCompetitorProductSearch((prev) => ({
                                    ...prev,
                                    [competitor.id]: e.target.value,
                                  }))
                                }
                                className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
                              />
                            </div>
                            {(() => {
                              const q = (
                                competitorProductSearch[competitor.id] || ''
                              ).toLowerCase()
                              const groups =
                                competitor.catalogs && competitor.catalogs.length
                                  ? competitor.catalogs
                                  : [{ id: 'all', name: null, products: competitor.products || [] }]
                              const multi = groups.length > 1
                              const anyMatch = groups.some((g) =>
                                (g.products || []).some((p) => p.name.toLowerCase().includes(q))
                              )
                              const renderItem = (product) => {
                                const isLinked = linkedCompetitorProductIds.has(product.id)
                                const isSelected =
                                  selectedCompetitorProducts[competitor.id] === product.id
                                return (
                                  <button
                                    key={product.id}
                                    onClick={() =>
                                      !isLinked &&
                                      handleSelectCompetitorProductClick(competitor.id, product.id)
                                    }
                                    disabled={isLinked}
                                    className={`w-full p-2 text-left rounded border transition-all flex items-center justify-between ${
                                      isLinked
                                        ? 'border-green-500 bg-green-50 dark:bg-green-900/20 cursor-not-allowed opacity-70'
                                        : isSelected
                                          ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                                          : 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800 hover:border-primary-500'
                                    }`}
                                  >
                                    <p className="text-sm font-medium truncate text-gray-900 dark:text-gray-100">
                                      <ProductName name={product.name} url={product.url} />
                                    </p>
                                    <span className="flex items-center gap-2 shrink-0">
                                      {isLinked && (
                                        <span className="text-xs text-green-600 dark:text-green-400 font-medium flex items-center gap-1">
                                          <Check className="h-3 w-3" />
                                          Связан
                                        </span>
                                      )}
                                      <span className="text-xs text-primary-600 dark:text-primary-400 font-semibold">
                                        {formatPrice(product.price)}
                                      </span>
                                    </span>
                                  </button>
                                )
                              }
                              return (
                                <div className="space-y-2">
                                  {!anyMatch && (
                                    <p className="text-sm text-gray-500 dark:text-gray-400 text-center py-4">
                                      {q ? 'Товары не найдены' : 'Нет товаров'}
                                    </p>
                                  )}
                                  {groups.map((cat) => {
                                    const items = (cat.products || []).filter((p) =>
                                      p.name.toLowerCase().includes(q)
                                    )
                                    if (q && items.length === 0) return null
                                    const key = `${competitor.id}:${cat.id}`
                                    const open = expandedCatalogs[key] ?? (!multi || !!q)
                                    if (!multi) {
                                      return (
                                        <div key={cat.id} className="space-y-1">
                                          {items.map(renderItem)}
                                        </div>
                                      )
                                    }
                                    return (
                                      <div
                                        key={cat.id}
                                        className="border border-gray-200 dark:border-gray-700 rounded-md"
                                      >
                                        <button
                                          onClick={() =>
                                            setExpandedCatalogs((prev) => ({
                                              ...prev,
                                              [key]: !open,
                                            }))
                                          }
                                          className="w-full flex items-center justify-between px-3 py-2 text-left hover:bg-gray-50 dark:hover:bg-gray-700/50 rounded-md"
                                        >
                                          <span className="text-sm font-medium text-gray-800 dark:text-gray-200 flex items-center gap-2">
                                            {open ? (
                                              <ChevronUp className="h-4 w-4" />
                                            ) : (
                                              <ChevronDown className="h-4 w-4" />
                                            )}
                                            {cat.name || 'Каталог'}
                                          </span>
                                          <span className="text-xs text-gray-500 dark:text-gray-400">
                                            {items.length} {productPlural(items.length)}
                                          </span>
                                        </button>
                                        {open && (
                                          <div className="space-y-1 p-2 pt-0">
                                            {items.length === 0 ? (
                                              <p className="text-xs text-gray-500 dark:text-gray-400 text-center py-2">
                                                Нет товаров
                                              </p>
                                            ) : (
                                              items.map(renderItem)
                                            )}
                                          </div>
                                        )}
                                      </div>
                                    )
                                  })}
                                </div>
                              )
                            })()}
                          </div>
                        )
                    )}
                  </div>
                </div>
              </div>
            )}
          </div>

          <div className="card">
            <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">
              Текущие связи ({analysis.product_links?.length || 0})
            </h4>
            {analysis.product_links?.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-700">
                        Мои товары
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-700">
                        Товары конкурента
                      </th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-700">
                        Сайт конкурента
                      </th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-700"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {reportGroups.flatMap((group) =>
                      group.links.map((link, i) => {
                        const partner = productToCompetitor[link.competitor_product?.id]
                        const partnerDomain = partner?.domain?.replace(/^https?:\/\//, '')
                        const partnerHref =
                          link.competitor_product?.url ||
                          (partnerDomain ? `https://${partnerDomain}` : null)
                        return (
                          <tr key={link.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                            {i === 0 && (
                              <td
                                rowSpan={group.links.length}
                                className="px-4 py-3 align-middle border-r border-gray-200 dark:border-gray-700"
                              >
                                <p className="font-medium text-sm text-gray-900 dark:text-gray-100">
                                  <ProductName name={group.userName} url={group.userUrl} />
                                </p>
                                <p className="text-xs text-gray-500 dark:text-gray-400">
                                  {formatPrice(group.userPrice)}
                                </p>
                              </td>
                            )}
                            <td className="px-4 py-3 align-top">
                              <p className="font-medium text-sm text-gray-900 dark:text-gray-100">
                                <ProductName name={link.competitor_product?.name} url={link.competitor_product?.url} />
                              </p>
                              <p className="text-xs text-gray-500 dark:text-gray-400">
                                {formatPrice(link.competitor_product?.price)}
                              </p>
                            </td>
                            <td className="px-4 py-3 align-top text-sm">
                              {partnerHref ? (
                                <a
                                  href={partnerHref}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-primary-600 dark:text-primary-400 hover:underline inline-flex items-center gap-1"
                                >
                                  <span className="truncate max-w-[180px]">
                                    {partnerDomain || 'Перейти'}
                                  </span>
                                  <ExternalLink className="h-3 w-3 shrink-0" />
                                </a>
                              ) : (
                                <span className="text-gray-400 dark:text-gray-500">—</span>
                              )}
                            </td>
                            <td className="px-4 py-3 align-top text-right">
                              {!isDemo && (
                                <button
                                  onClick={() => unlinkProducts(link.id)}
                                  className="p-2 text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition-colors"
                                  title="Удалить связь"
                                >
                                  <Trash2 className="h-4 w-4" />
                                </button>
                              )}
                            </td>
                          </tr>
                        )
                      })
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <p className="text-gray-500 dark:text-gray-400">Нет связанных товаров</p>
            )}
          </div>
        </div>
      )}

      {activeTab === 'competitors' && (
        <div className="space-y-6">
          {competitorList.length > 0 ? (
            competitorList.map((comp, index) => (
              <div key={comp.id} className="card">
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center space-x-4">
                    <span className="w-8 h-8 bg-primary-100 dark:bg-primary-900 text-primary-600 dark:text-primary-400 rounded-full flex items-center justify-center font-semibold">
                      {index + 1}
                    </span>
                    <div>
                      <a
                        href={`https://${baseDomain(comp.domain)}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300 hover:underline"
                      >
                        {baseDomain(comp.domain)}
                      </a>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {comp.products?.length || 0} {productPlural(comp.products?.length || 0)}
                        {comp.competitor_type ? ` • ${comp.competitor_type}` : ''}
                        {comp.last_price_update && (
                          <span className="ml-2">
                            • Цены актуальны на{' '}
                            {new Date(comp.last_price_update).toLocaleDateString('ru-RU', {
                              day: 'numeric',
                              month: 'long',
                              year: 'numeric',
                            })}{' '}
                            {new Date(comp.last_price_update).toLocaleTimeString('ru-RU', {
                              hour: '2-digit',
                              minute: '2-digit',
                            })}{' '}
                            (UTC)
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    {!isDemo && (
                      <button
                        onClick={() => setAddCatalogTarget(comp)}
                        className="btn-secondary text-sm flex items-center space-x-2"
                      >
                        <Plus className="h-4 w-4" />
                        <span>Добавить товары</span>
                      </button>
                    )}
                    {isDemo ? (
                      <button
                        onClick={() => showError('Настройка селекторов недоступна в демо-режиме')}
                        className="btn-secondary text-sm flex items-center space-x-2"
                      >
                        <Settings className="h-4 w-4" />
                        <span>Настроить</span>
                      </button>
                    ) : (
                      <Link
                        to={`/analysis/${id}/competitor/${comp.id}/selectors`}
                        className="btn-secondary text-sm flex items-center space-x-2"
                      >
                        <Settings className="h-4 w-4" />
                        <span>Настроить</span>
                      </Link>
                    )}
                    {comp.products?.length > 0 && (
                      <button
                        onClick={() => handleUpdatePrices(comp.id)}
                        disabled={isUpdatingPrices}
                        className="btn-secondary text-sm flex items-center space-x-2"
                      >
                        <RefreshCw
                          className={`h-4 w-4 ${isUpdatingPrices ? 'animate-spin' : ''}`}
                        />
                        <span>Обновить</span>
                      </button>
                    )}
                  </div>
                </div>
                {comp.products?.length > 0 ? (
                  renderCatalogGroups(comp, 'text-gray-600 dark:text-gray-400')
                ) : (
                  <div className="text-center py-8">
                    <p className="text-gray-500 dark:text-gray-400">
                      Нет товаров. Настройте селекторы
                    </p>
                  </div>
                )}
              </div>
            ))
          ) : (
            <div className="card text-center py-8">
              <p className="text-gray-500 dark:text-gray-400">Конкуренты не найдены</p>
            </div>
          )}
        </div>
      )}

      {addCatalogTarget && (
        <AddCatalogModal
          competitor={addCatalogTarget}
          onClose={() => setAddCatalogTarget(null)}
          onAdded={() => fetchAnalysis()}
        />
      )}

      {showHowItWorksModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-2xl w-full p-6">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Как работает связывание товаров
              </h3>
              <button
                onClick={() => setShowHowItWorksModal(false)}
                className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                <X className="h-5 w-5 text-gray-500 dark:text-gray-400" />
              </button>
            </div>

            <div className="space-y-4 text-gray-700 dark:text-gray-300">
              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-primary-100 dark:bg-primary-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-primary-600 dark:text-primary-400 font-semibold text-sm">
                    1
                  </span>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white mb-1">
                    Выберите ваш товар
                  </h4>
                  <p className="text-sm">
                    В первом блоке отображаются товары с вашего сайта. Кликните на товар, чтобы
                    выбрать его для связывания.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-primary-100 dark:bg-primary-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-primary-600 dark:text-primary-400 font-semibold text-sm">
                    2
                  </span>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white mb-1">
                    Выберите товар конкурента
                  </h4>
                  <p className="text-sm">
                    В нижних блоках показаны товары конкурентов. Выберите аналогичный товар
                    конкурента для создания связи.
                  </p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-primary-100 dark:bg-primary-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-primary-600 dark:text-primary-400 font-semibold text-sm">
                    3
                  </span>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white mb-1">Свяжите товары</h4>
                  <p className="text-sm">
                    После выбора обоих товаров нажмите кнопку «Связать», чтобы создать связь между
                    ними. Эта связь будет использоваться для сравнения цен в отчёте.
                  </p>
                </div>
              </div>

              <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">Важно:</h4>
                <ul className="text-sm space-y-1 text-blue-800 dark:text-blue-200">
                  <li>
                    • Один товар с вашего сайта можно связать только с одним товаром конкурента
                  </li>
                  <li>• Связи используются для формирования отчёта по сравнению цен</li>
                  <li>
                    • Вы можете удалить связь в любое время, нажав на значок корзины в таблице
                    «Текущие связи»
                  </li>
                </ul>
              </div>
            </div>

            <div className="flex justify-end mt-6">
              <button onClick={() => setShowHowItWorksModal(false)} className="btn-primary">
                Понятно
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
