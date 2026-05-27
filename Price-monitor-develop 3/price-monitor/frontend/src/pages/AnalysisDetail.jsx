import { useState, useEffect } from 'react'
import { useParams, Link, useLocation } from 'react-router-dom'
import api from '../utils/api'
import { ArrowLeft, Download, Table, Link as LinkIcon, X, Check, Settings, Trash2, Edit3, Save, XCircle, RefreshCw, ExternalLink } from 'lucide-react'
import { getRegionName } from '../utils/regions'
import { exportToExcel, exportToCSV, formatPrice, formatDate } from '../utils/export'
import { PriceComparisonChart, PriceDifferenceChart } from '../components/Charts'
import { PriceDynamicsChart } from '../components/PriceDynamicsChart'
import { useToast } from '../context/ToastContext'

const DEMO_DATA = {
  1: {
    id: 1, analysis_type: 'auto', region: '213',
    queries: ['iPhone 15 Pro', 'Samsung Galaxy S24'],
    user_site: 'example.ru',
    created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    competitors: [
      {
        id: 101, domain: 'mvideo.ru', is_user_site: false,
        title_selector: '.product-title', price_selector: '.product-price',
        products: [
          { id: 201, name: 'iPhone 15 Pro 128GB', price: 89990, currency: 'RUB' },
          { id: 202, name: 'iPhone 15 Pro 256GB', price: 99990, currency: 'RUB' },
          { id: 203, name: 'Samsung Galaxy S24 256GB', price: 79990, currency: 'RUB' },
        ]
      },
      {
        id: 102, domain: 'citilink.ru', is_user_site: false,
        title_selector: '.product_name', price_selector: '.current-price',
        products: [
          { id: 204, name: 'iPhone 15 Pro 128GB Natural Titanium', price: 87990, currency: 'RUB' },
          { id: 205, name: 'Samsung Galaxy S24 Ultra 512GB', price: 109990, currency: 'RUB' },
        ]
      },
      {
        id: 103, domain: 'example.ru', is_user_site: true,
        title_selector: null, price_selector: null,
        products: [
          { id: 206, name: 'iPhone 15 Pro 128GB', price: 94990, currency: 'RUB' },
          { id: 207, name: 'iPhone 15 Pro 256GB', price: 104990, currency: 'RUB' },
          { id: 208, name: 'Samsung Galaxy S24 256GB', price: 84990, currency: 'RUB' },
          { id: 209, name: 'Samsung Galaxy S24 Ultra 512GB', price: 114990, currency: 'RUB' },
        ]
      },
    ],
    product_links: [
      { user_product_id: 206, competitor_product_id: 201 },
      { user_product_id: 207, competitor_product_id: 202 },
      { user_product_id: 208, competitor_product_id: 203 },
      { user_product_id: 209, competitor_product_id: 205 },
    ]
  },
  2: {
    id: 2, analysis_type: 'manual', region: '2',
    queries: ['Ноутбук Dell XPS'],
    user_site: 'myshop.ru',
    created_at: new Date(Date.now() - 5 * 86400000).toISOString(),
    competitors: [
      {
        id: 104, domain: 'dns-shop.ru', is_user_site: false,
        title_selector: '.catalog-product__name', price_selector: '.product-price__current',
        products: [
          { id: 210, name: 'Ноутбук Dell XPS 13 9310', price: 119990, currency: 'RUB' },
          { id: 211, name: 'Ноутбук Dell XPS 15 9520', price: 159990, currency: 'RUB' },
          { id: 212, name: 'Ноутбук Dell XPS 17 9720', price: 189990, currency: 'RUB' },
        ]
      },
      {
        id: 105, domain: 'eldorado.ru', is_user_site: false,
        title_selector: '.product__title', price_selector: '.product__price',
        products: [
          { id: 213, name: 'Dell XPS 13 Plus 9320', price: 134990, currency: 'RUB' },
          { id: 214, name: 'Dell XPS 15 9530', price: 169990, currency: 'RUB' },
        ]
      },
      {
        id: 106, domain: 'myshop.ru', is_user_site: true,
        title_selector: null, price_selector: null,
        products: [
          { id: 215, name: 'Ноутбук Dell XPS 13', price: 124990, currency: 'RUB' },
          { id: 216, name: 'Ноутбук Dell XPS 15', price: 164990, currency: 'RUB' },
          { id: 217, name: 'Ноутбук Dell XPS 17', price: 199990, currency: 'RUB' },
        ]
      },
    ],
    product_links: [
      { user_product_id: 215, competitor_product_id: 210 },
      { user_product_id: 216, competitor_product_id: 211 },
      { user_product_id: 217, competitor_product_id: 212 },
    ]
  },
  3: {
    id: 3, analysis_type: 'auto', region: '213',
    queries: ['Sony PlayStation 5'],
    user_site: 'gamezone.ru',
    created_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    competitors: [
      {
        id: 107, domain: 'mvideo.ru', is_user_site: false,
        title_selector: '.product-title', price_selector: '.product-price',
        products: [
          { id: 218, name: 'Sony PlayStation 5 Digital Edition', price: 45990, currency: 'RUB' },
          { id: 219, name: 'Sony PlayStation 5 Slim', price: 52990, currency: 'RUB' },
          { id: 220, name: 'DualSense Wireless Controller', price: 6990, currency: 'RUB' },
        ]
      },
      {
        id: 108, domain: 'gamepark.ru', is_user_site: false,
        title_selector: '.card__title', price_selector: '.card__price',
        products: [
          { id: 221, name: 'PS5 Digital Edition + FIFA 24', price: 49990, currency: 'RUB' },
          { id: 222, name: 'Sony PlayStation 5 Pro', price: 74990, currency: 'RUB' },
        ]
      },
      {
        id: 109, domain: 'gamezone.ru', is_user_site: true,
        title_selector: null, price_selector: null,
        products: [
          { id: 223, name: 'Sony PlayStation 5 Digital', price: 47990, currency: 'RUB' },
          { id: 224, name: 'Sony PlayStation 5 Slim', price: 54990, currency: 'RUB' },
          { id: 225, name: 'PS5 DualSense Controller', price: 7490, currency: 'RUB' },
          { id: 226, name: 'Sony PlayStation 5 Pro', price: 79990, currency: 'RUB' },
        ]
      },
    ],
    product_links: [
      { user_product_id: 223, competitor_product_id: 218 },
      { user_product_id: 224, competitor_product_id: 219 },
      { user_product_id: 225, competitor_product_id: 220 },
      { user_product_id: 226, competitor_product_id: 222 },
    ]
  }
}

export default function AnalysisDetail() {
  const { id } = useParams()
  const location = useLocation()
  const [analysis, setAnalysis] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('report')
  const [linkingMode, setLinkingMode] = useState(null)
  const [selectedProduct, setSelectedProduct] = useState(null)
  const [selectedCompetitorProduct, setSelectedCompetitorProduct] = useState(null)
  const [userSiteUrl, setUserSiteUrl] = useState('')
  const [userSiteStatus, setUserSiteStatus] = useState(null)
  const [isEditingName, setIsEditingName] = useState(false)
  const [editingName, setEditingName] = useState('')
  const [isUpdatingPrices, setIsUpdatingPrices] = useState(false)
  const [priceDynamicsData, setPriceDynamicsData] = useState(null)
  const [showEditDomainModal, setShowEditDomainModal] = useState(false)
  const [editingDomain, setEditingDomain] = useState('')
  const [editingTitleSelector, setEditingTitleSelector] = useState('')
  const [editingPriceSelector, setEditingPriceSelector] = useState('')
  const [showHowItWorksModal, setShowHowItWorksModal] = useState(false)
  const { error: showError, success } = useToast()
  const isDemo = location.state?.demo === true

  useEffect(() => {
    fetchAnalysis()
  }, [id])

  useEffect(() => {
    if (analysis && analysis.product_links && analysis.product_links.length > 0) {
      fetchPriceDynamics()
    }
  }, [analysis])

  const fetchAnalysis = async () => {
    if (isDemo && DEMO_DATA[id]) {
      setAnalysis(DEMO_DATA[id])
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
        // Fetch updated analysis data
        await fetchAnalysis()

        if (competitorId) {
          success('Цены успешно обновлены')
        } else {
          if (result.overall_status === 'success') {
            success('Цены успешно обновлены по всем конкурентам')
          } else if (result.overall_status === 'partial') {
            showError(`По некоторым конкурентам не удалось обновить цену. Обновлено: ${result.success_count}, частично: ${result.partial_count}, ошибок: ${result.error_count}`)
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
        showError(error.response.data?.message || 'Слишком частые запросы. Попробуйте через 3 минуты.')
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
      // Demo data for price dynamics
      setPriceDynamicsData([
        {
          product_name: 'iPhone 15 Pro 128GB',
          user_site: true,
          competitor_name: 'iPhone 15 Pro 128GB',
          competitor_domain: 'mvideo.ru',
          product_url: 'https://mvideo.ru/product/1',
          data_points: [
            { date: new Date(Date.now() - 7 * 86400000).toISOString().split('T')[0], user_price: 94990, competitor_price: 89990 },
            { date: new Date(Date.now() - 3 * 86400000).toISOString().split('T')[0], user_price: 93990, competitor_price: 88990 },
            { date: new Date().toISOString().split('T')[0], user_price: 94990, competitor_price: 89990 }
          ]
        }
      ])
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
      setAnalysis(prev => ({ ...prev, name: editingName.trim() }))
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

  const handleEditDomainClick = () => {
    if (userCompetitor) {
      setEditingDomain(userCompetitor.domain || '')
      setEditingTitleSelector(userCompetitor.title_selector || '')
      setEditingPriceSelector(userCompetitor.price_selector || '')
      setShowEditDomainModal(true)
    }
  }

  const handleSaveDomainAndSelectors = async () => {
    if (!editingDomain.trim() || !editingTitleSelector.trim() || !editingPriceSelector.trim()) {
      showError('Домен и селекторы не могут быть пустыми')
      return
    }
    try {
      await api.put(`/analysis/competitor/${userCompetitor.id}`, {
        url: editingDomain.trim(),
        title_selector: editingTitleSelector.trim(),
        price_selector: editingPriceSelector.trim()
      })
      await fetchAnalysis()
      setShowEditDomainModal(false)
      success('Домен и селекторы обновлены')
    } catch (error) {
      console.error('Error updating domain and selectors:', error)
      showError('Ошибка при обновлении домена и селекторов')
    }
  }

  const handleExportExcel = () => {
    console.log('Export Excel clicked, product_links:', analysis?.product_links?.length)
    if (!analysis?.product_links?.length) {
      showError('Нет данных для экспорта. Сначала свяжите товары.')
      return
    }

    const data = analysis.product_links.map(link => ({
      'Товар конкурента': link.competitor_product?.name || 'N/A',
      'Ваш товар': link.user_product?.name || 'N/A',
      'Ваша цена': link.user_product?.price || 'N/A',
      'Цена конкурента': link.competitor_product?.price || 'N/A',
      'Разница (₽)': link.price_difference !== null
        ? `${link.price_difference >= 0 ? '+' : '-'}${Math.abs(link.price_difference)}`
        : 'N/A'
    }))

    console.log('Exporting to Excel, data:', data.length, 'rows')
    exportToExcel(data, `analysis_${id}_${Date.now()}`)
  }

  const handleExportCSV = () => {
    console.log('Export CSV clicked, product_links:', analysis?.product_links?.length)
    if (!analysis?.product_links?.length) {
      showError('Нет данных для экспорта. Сначала свяжите товары.')
      return
    }

    const data = analysis.product_links.map(link => ({
      'Товар конкурента': link.competitor_product?.name || 'N/A',
      'Ваш товар': link.user_product?.name || 'N/A',
      'Ваша цена': link.user_product?.price || 'N/A',
      'Цена конкурента': link.competitor_product?.price || 'N/A',
      'Разница (₽)': link.price_difference !== null
        ? `${link.price_difference >= 0 ? '+' : '-'}${Math.abs(link.price_difference)}`
        : 'N/A'
    }))

    console.log('Exporting to CSV, data:', data.length, 'rows')
    exportToCSV(data, `analysis_${id}_${Date.now()}`)
  }

  const linkProducts = async (userProductId, competitorProductId) => {
    try {
      await api.post('/analysis/link', {
        analysis_id: parseInt(id),
        user_product_id: userProductId,
        competitor_product_id: competitorProductId
      })
      await fetchAnalysis()
      setLinkingMode(null)
      setSelectedProduct(null)
      setSelectedCompetitorProduct(null)
    } catch (error) {
      console.error('Error linking products:', error)
    }
  }

  const handleSelectCompetitorProduct = async (competitorProductId) => {
    if (!selectedProduct) return
    try {
      await api.post('/analysis/link', {
        analysis_id: parseInt(id),
        user_product_id: selectedProduct.id,
        competitor_product_id: competitorProductId
      })
      await fetchAnalysis()
      setLinkingMode(null)
      setSelectedProduct(null)
      setSelectedCompetitorProduct(null)
    } catch (error) {
      console.error('Error linking products:', error)
    }
  }

  const unlinkProducts = async (linkId) => {
    if (isDemo) {
      // Для демо-режима просто обновляем локальное состояние
      setAnalysis(prev => ({
        ...prev,
        product_links: prev.product_links.filter(link => link.id !== linkId)
      }))
      return
    }

    try {
      await api.delete(`/analysis/unlink/${linkId}`)
      await fetchAnalysis()
    } catch (error) {
      console.error('Error unlinking products:', error)
      // Если API недоступно, обновляем локальное состояние
      setAnalysis(prev => ({
        ...prev,
        product_links: prev.product_links.filter(link => link.id !== linkId)
      }))
    }
  }

  const handleSelectCompetitorProductClick = (productId) => {
    if (selectedCompetitorProduct === productId) {
      setSelectedCompetitorProduct(null)
    } else {
      setSelectedCompetitorProduct(productId)
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!analysis) {
    return (
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 text-center">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">Анализ не найден</h2>
        <Link to="/dashboard" className="btn-primary">Вернуться к списку</Link>
      </div>
    )
  }

  const userCompetitor = analysis.competitors?.find(c => c.is_user_site)
  const competitorList = analysis.competitors?.filter(c => !c.is_user_site) || []

  const chartData = analysis.product_links?.map(link => ({
    competitor: link.competitor_product?.name,
    user_price: link.user_product?.price,
    competitor_price: link.competitor_product?.price,
    price_difference: link.price_difference,
    competitor_product: link.competitor_product?.name
  })) || []

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      <div className="mb-6">
        <Link to="/dashboard" state={{ demo: isDemo }} className="flex items-center text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white mb-4">
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
                <button onClick={handleUpdateName} className="p-1.5 text-green-600 hover:bg-green-100 dark:hover:bg-green-900/30 rounded transition-colors">
                  <Save className="h-5 w-5" />
                </button>
                <button onClick={cancelEditingName} className="p-1.5 text-red-600 hover:bg-red-100 dark:hover:bg-red-900/30 rounded transition-colors">
                  <XCircle className="h-5 w-5" />
                </button>
              </div>
            ) : (
              <div className="flex items-center space-x-2 mb-2">
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                  {analysis.name || `Анализ #${analysis.id}`}
                </h1>
                {!isDemo && (
                  <button onClick={startEditingName} className="p-1.5 text-gray-400 hover:text-primary-600 dark:hover:text-primary-400 transition-colors">
                    <Edit3 className="h-4 w-4" />
                  </button>
                )}
              </div>
            )}
            <p className="text-gray-600 dark:text-gray-400">
              {formatDate(analysis.created_at)} {new Date(analysis.created_at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })} (UTC) • Регион: {getRegionName(analysis.region)}
            </p>
            {/* Price update status for analysis */}
            {!isDemo && (userCompetitor?.products?.length > 0 || competitorList.some(c => c.products?.length > 0)) && (
              <div className="mt-2 flex items-center space-x-3">
                <button
                  onClick={() => handleUpdatePrices()}
                  disabled={isUpdatingPrices}
                  className="btn-primary text-sm flex items-center space-x-2"
                >
                  <RefreshCw className={`h-4 w-4 ${isUpdatingPrices ? 'animate-spin' : ''}`} />
                  <span>Обновить цены</span>
                </button>
                {userCompetitor?.last_price_update && (
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Цены актуальны на {new Date(userCompetitor.last_price_update).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })} {new Date(userCompetitor.last_price_update).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })} (UTC)
                  </p>
                )}
              </div>
            )}
          </div>
          <div className="flex items-center space-x-2">
            <button onClick={handleExportExcel} className="btn-secondary flex items-center space-x-2">
              <Download className="h-4 w-4" />
              <span>Excel</span>
            </button>
            <button onClick={handleExportCSV} className="btn-secondary flex items-center space-x-2">
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
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'report'
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600'
              }`}
          >
            Отчёт
          </button>
          <button
            onClick={() => setActiveTab('products')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'products'
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600'
              }`}
          >
            Ваши товары ({userCompetitor?.products?.length || 0})
          </button>
          <button
            onClick={() => setActiveTab('competitors')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'competitors'
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300 dark:text-gray-400 dark:hover:text-gray-200 dark:hover:border-gray-600'
              }`}
          >
            Конкуренты ({competitorList.length})
          </button>
          <button
            onClick={() => setActiveTab('linking')}
            className={`pb-4 px-1 border-b-2 font-medium text-sm ${activeTab === 'linking'
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
          {/* Price Dynamics Chart Block */}
          {analysis.product_links && analysis.product_links.length > 0 && (
            <div className="card flex justify-center">
              <div className="w-full max-w-full">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    График динамики цен
                  </h3>
                </div>
                {priceDynamicsData && priceDynamicsData.length > 0 ? (
                  <PriceDynamicsChart
                    data={priceDynamicsData}
                    dateRange={{
                      start: analysis.created_at,
                      end: new Date().toISOString()
                    }}
                  />
                ) : (
                  <div className="text-center py-8">
                    <p className="text-gray-500 dark:text-gray-400">Нет данных для построения графика</p>
                    <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
                      График появится автоматически, когда у вас и конкурентов будут товары с историей цен
                    </p>
                  </div>
                )}
              </div>
            </div>
          )}

          <div className="card">
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">Сводный отчёт</h3>

            {(!analysis.product_links || analysis.product_links.length === 0) ? (
              <div className="text-center py-8">
                <p className="text-gray-500 dark:text-gray-400 mb-4">Нет данных для отображения</p>
                <p className="text-sm text-gray-400 dark:text-gray-500">
                  Сначала добавьте товары своего сайта через <button onClick={() => setActiveTab('products')} className="text-primary-600 dark:text-primary-400 hover:underline font-medium">вкладку "Ваши товары"</button> (настройте селекторы и соберите товары), затем <button onClick={() => setActiveTab('competitors')} className="text-primary-600 dark:text-primary-400 hover:underline font-medium">добавьте товары конкурентов</button> и после свяжите через <button onClick={() => setActiveTab('linking')} className="text-primary-600 dark:text-primary-400 hover:underline font-medium">раздел "Связывание"</button>
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">Ваш товар</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">Ваша цена</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">Товар конкурента</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">Цена конкурента</th>
                      <th className="px-4 py-3 text-left text-sm font-medium text-gray-700 dark:text-gray-300">Разница</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {analysis.product_links.map((link) => (
                      <tr key={link.id} className="hover:bg-gray-50 dark:hover:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
                        <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                          {link.user_product?.name || 'N/A'}
                        </td>
                        <td className="px-4 py-3 text-sm font-medium text-gray-900 dark:text-gray-100">
                          {formatPrice(link.user_product?.price)}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                          {link.competitor_product?.name || 'N/A'}
                        </td>
                        <td className="px-4 py-3 text-sm text-gray-900 dark:text-gray-100">
                          {formatPrice(link.competitor_product?.price)}
                        </td>
                        <td className={`px-4 py-3 text-sm font-medium ${link.price_difference > 0 ? 'text-red-600 dark:text-red-400' :
                          link.price_difference < 0 ? 'text-green-600 dark:text-green-400' : 'text-gray-900 dark:text-gray-100'
                          }`}>
                          {link.price_difference !== null
                            ? `${link.price_difference > 0 ? '+' : link.price_difference < 0 ? "-" : ""}${formatPrice(Math.abs(link.price_difference))}`
                            : 'N/A'}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {analysis.product_links?.length > 0 && (
            <div className="grid md:grid-cols-3 gap-4">
              <div className="card text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400">Всего позиций</p>
                <p className="text-2xl font-bold text-gray-900 dark:text-gray-100">{analysis.product_links.length}</p>
              </div>
              <div className="card text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400">Выше ценой</p>
                <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                  {analysis.product_links.filter(l => l.price_difference > 0).length}
                </p>
              </div>
              <div className="card text-center">
                <p className="text-sm text-gray-500 dark:text-gray-400">Ниже ценой</p>
                <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                  {analysis.product_links.filter(l => l.price_difference < 0).length}
                </p>
              </div>
            </div>
          )}
        </div>
      )}

      {activeTab === 'charts' && (
        <div className="space-y-6">
          {chartData.length > 0 ? (
            <>
              <div className="card">
                <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">Сравнение цен</h3>
                <div className="h-80">
                  <PriceComparisonChart data={chartData} />
                </div>
              </div>
              <div className="card">
                <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">Разница в ценах</h3>
                <div className="h-80">
                  <PriceDifferenceChart data={chartData} />
                </div>
              </div>
            </>
          ) : (
            <div className="card text-center py-12">
              <p className="text-gray-500 dark:text-gray-400">Нет данных для графиков</p>
              <p className="text-sm text-gray-400 dark:text-gray-500 mt-2">
                Свяжите товары на вкладке "Связывание" для отображения графиков
              </p>
            </div>
          )}
        </div>
      )}

      {activeTab === 'products' && (
        <div className="space-y-6">
          {userCompetitor && (
            <div className="card">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Ваши товары
                  <span className="text-sm font-normal text-gray-500 dark:text-gray-400 ml-2">
                    ({userCompetitor.products?.length || 0})
                  </span>
                  {analysis.user_site && (
                    <a
                      href={`https://${analysis.user_site.replace(/^https?:\/\//, '')}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm font-normal text-primary-600 dark:text-primary-400 ml-3 hover:underline"
                    >
                      {analysis.user_site}
                    </a>
                  )}
                </h3>
                <div className="flex items-center space-x-2">
                  {!isDemo && userCompetitor.products?.length > 0 && (
                    <Link
                      to={`/analysis/${id}/competitor/${userCompetitor.id}/selectors`}
                      className="btn-secondary text-sm flex items-center space-x-2"
                    >
                      <Settings className="h-4 w-4" />
                      <span>Настроить</span>
                    </Link>
                  )}
                  {!isDemo && userCompetitor.products?.length > 0 && (
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
              {/* Display domain above price actuality */}
              {userCompetitor.domain && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-2">
                  <a
                    href={`https://${userCompetitor.domain.replace(/^https?:\/\//, '')}`}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300 hover:underline"
                  >
                    {userCompetitor.domain}
                  </a>
                </p>
              )}
              {userCompetitor.last_price_update && (
                <p className="text-xs text-gray-500 dark:text-gray-400 mb-3">
                  Цены актуальны на {new Date(userCompetitor.last_price_update).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })} {new Date(userCompetitor.last_price_update).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })} (UTC)
                </p>
              )}
              {userCompetitor.products?.length > 0 ? (
                <div className="space-y-2 max-h-96 overflow-y-auto">
                  {userCompetitor.products.map(product => (
                    <div key={product.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border-b border-gray-200 dark:border-gray-700">
                      <p className="font-medium text-gray-900 dark:text-gray-100">{product.name}</p>
                      <div className="flex items-center space-x-4 mt-1">
                        <p className="text-primary-600 dark:text-primary-400 font-semibold">{formatPrice(product.price)}</p>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-gray-500 dark:text-gray-400 mb-4">Нет товаров</p>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                      URL вашего сайта
                    </label>
                    <div className="flex items-center space-x-2">
                      <input
                        type="text"
                        value={userSiteUrl}
                        onChange={(e) => setUserSiteUrl(e.target.value)}
                        placeholder="Ваш сайт (например: example.ru)"
                        className="input-field flex-1"
                      />
                    </div>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Укажите URL вашего сайта, затем настройте селекторы и соберите товары
                    </p>
                    {userCompetitor && (
                      <Link
                        to={`/analysis/${id}/competitor/${userCompetitor.id}/selectors`}
                        className="btn-primary text-sm inline-flex items-center space-x-1 mt-3"
                      >
                        <Settings className="h-4 w-4" />
                        <span>Настроить селекторы и собрать товары</span>
                      </Link>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {activeTab === 'linking' && (
        <div className="card">
          <div className="flex items-center justify-between mb-6">
            <div>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Связывание товаров</h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Свяжите ваши товары с товарами конкурентов для формирования отчёта
              </p>
            </div>
            {linkingMode ? (
              <div className="flex items-center space-x-2">
                <button
                  onClick={() => setShowHowItWorksModal(true)}
                  className="btn-secondary flex items-center space-x-2"
                >
                  <span>Как это работает?</span>
                </button>
                <button
                  onClick={() => { setLinkingMode(null); setSelectedProduct(null); }}
                  className="btn-secondary flex items-center space-x-2"
                >
                  <X className="h-4 w-4" />
                  <span>Отмена</span>
                </button>
              </div>
            ) : (
              <button
                onClick={() => setLinkingMode('user')}
                className="btn-primary flex items-center space-x-2"
              >
                <LinkIcon className="h-4 w-4" />
                <span>Связать товары</span>
              </button>
            )}
          </div>

          {linkingMode === 'user' && (
            <div className="mb-6 p-4 bg-primary-50 dark:bg-primary-900/30 rounded-lg">
              <p className="text-sm text-primary-700 dark:text-primary-300 mb-2">Выберите ваш товар:</p>
              <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-2">
                {userCompetitor?.products?.map(product => (
                  <button
                    key={product.id}
                    onClick={() => setSelectedProduct(product)}
                    className={`p-3 text-left rounded-lg border-2 transition-all ${selectedProduct?.id === product.id
                      ? 'border-primary-500 bg-white dark:bg-gray-800'
                      : 'border-gray-200 bg-white hover:border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-gray-600'
                      }`}
                  >
                    <p className="text-sm font-medium truncate text-gray-900 dark:text-gray-100">{product.name}</p>
                    <p className="text-xs text-gray-500 dark:text-gray-400">{formatPrice(product.price)}</p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {linkingMode === 'competitor' && selectedProduct && (
            <div className="mb-6 p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
              <p className="text-sm text-gray-700 dark:text-gray-300 mb-2">
                Выбранный товар: <strong>{selectedProduct.name}</strong>
              </p>
              <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">Выберите один товар конкурента:</p>
              <div className="space-y-4 max-h-96 overflow-y-auto">
                {competitorList.map(competitor => (
                  !competitor.is_user_site && competitor.products?.length > 0 && (
                    <div key={competitor.id} className="mb-4">
                      <h5 className="font-medium text-gray-900 dark:text-gray-100 mb-2 flex items-center">
                        <a
                          href={`https://${competitor.domain.replace(/^https?:\/\//, '')}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary-600 dark:text-primary-400 hover:underline"
                        >
                          {competitor.domain}
                        </a>
                        <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">({competitor.products.length} товаров)</span>
                      </h5>
                      <div className="grid gap-2">
                        {competitor.products.map(product => (
                          <button
                            key={product.id}
                            onClick={() => handleSelectCompetitorProductClick(product.id)}
                            className={`p-3 text-left rounded-lg border-2 transition-all flex items-center justify-between w-full ${selectedCompetitorProduct === product.id
                              ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                              : 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800 hover:border-primary-500'
                              }`}
                          >
                            <div className="flex items-center space-x-3">
                              <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${selectedCompetitorProduct === product.id
                                ? 'border-primary-500 bg-primary-500'
                                : 'border-gray-300'
                                }`}>
                                {selectedCompetitorProduct === product.id && (
                                  <Check className="h-3 w-3 text-white" />
                                )}
                              </div>
                              <p className="font-medium text-gray-900 dark:text-gray-100">{product.name}</p>
                            </div>
                            <span className="text-primary-600 dark:text-primary-400 font-semibold">{formatPrice(product.price)}</span>
                          </button>
                        ))}
                      </div>
                    </div>
                  )
                ))}
              </div>
              {selectedCompetitorProduct && (
                <div className="mt-4 flex items-center justify-between">
                  <p className="text-sm text-gray-600 dark:text-gray-400">
                    Выбран 1 товар
                  </p>
                  <button
                    onClick={() => handleSelectCompetitorProduct(selectedCompetitorProduct)}
                    className="btn-primary"
                  >
                    Связать
                  </button>
                </div>
              )}
            </div>
          )}

          {linkingMode && (
            <div className="mb-6 grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="p-4 bg-primary-50 dark:bg-primary-900/30 rounded-lg">
                <h5 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Ваши товары</h5>
                <div className="space-y-2 max-h-64 overflow-y-auto">
                  {userCompetitor?.products?.map(product => (
                    <button
                      key={product.id}
                      onClick={() => setSelectedProduct(product)}
                      className={`w-full p-2 text-left rounded border transition-all ${selectedProduct?.id === product.id
                        ? 'border-primary-500 bg-white dark:bg-gray-800'
                        : 'border-gray-200 bg-white hover:border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:hover:border-gray-600'
                        }`}
                    >
                      <p className="text-sm font-medium truncate text-gray-900 dark:text-gray-100">{product.name}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">{formatPrice(product.price)}</p>
                    </button>
                  ))}
                </div>
              </div>
              <div className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg">
                <h5 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Товары конкурентов</h5>
                <div className="space-y-4 max-h-64 overflow-y-auto">
                  {competitorList.map(competitor => (
                    !competitor.is_user_site && competitor.products?.length > 0 && (
                      <div key={competitor.id} className="mb-2">
                        <h6 className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">{competitor.domain}</h6>
                        <div className="space-y-1">
                          {competitor.products.map(product => (
                            <button
                              key={product.id}
                              onClick={() => handleSelectCompetitorProductClick(product.id)}
                              className={`w-full p-2 text-left rounded border transition-all flex items-center justify-between ${selectedCompetitorProduct === product.id
                                ? 'border-primary-500 bg-primary-50 dark:bg-primary-900/30'
                                : 'border-gray-200 bg-white dark:border-gray-700 dark:bg-gray-800 hover:border-primary-500'
                                }`}
                            >
                              <p className="text-sm font-medium truncate text-gray-900 dark:text-gray-100">{product.name}</p>
                              <span className="text-xs text-primary-600 dark:text-primary-400 font-semibold">{formatPrice(product.price)}</span>
                            </button>
                          ))}
                        </div>
                      </div>
                    )
                  ))}
                </div>
              </div>
            </div>
          )}

          {selectedProduct && !linkingMode && (
            <div className="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/30 rounded-lg">
              <p className="text-sm text-yellow-700 dark:text-yellow-300">
                Выбран товар: <strong>{selectedProduct.name}</strong> ({formatPrice(selectedProduct.price)})
              </p>
              <button
                onClick={() => setLinkingMode('competitor')}
                className="btn-primary mt-3"
              >
                Выбрать товар конкурента
              </button>
            </div>
          )}

          <div className="border-t border-gray-200 dark:border-gray-700 pt-6 mt-6">
            <h4 className="font-medium text-gray-900 dark:text-gray-100 mb-3">Текущие связи ({analysis.product_links?.length || 0})</h4>
            {analysis.product_links?.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead className="bg-gray-50 dark:bg-gray-800">
                    <tr>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-700">Мои товары</th>
                      <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-700">Товары конкурента</th>
                      <th className="px-4 py-3 text-right text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-700"></th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                    {analysis.product_links.map(link => (
                      <tr key={link.id} className="hover:bg-gray-50 dark:hover:bg-gray-800/50">
                        <td className="px-4 py-3 align-top">
                          <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{link.user_product?.name || 'N/A'}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">{formatPrice(link.user_product?.price)}</p>
                        </td>
                        <td className="px-4 py-3 align-top">
                          <p className="font-medium text-sm text-gray-900 dark:text-gray-100">{link.competitor_product?.name || 'N/A'}</p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">{formatPrice(link.competitor_product?.price)}</p>
                        </td>
                        <td className="px-4 py-3 align-top text-right">
                          <button
                            onClick={() => unlinkProducts(link.id)}
                            className="p-2 text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition-colors"
                            title="Удалить связь"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </td>
                      </tr>
                    ))}
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
                        href={`https://${comp.domain}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="font-medium text-primary-600 hover:text-primary-500 dark:text-primary-400 dark:hover:text-primary-300 hover:underline"
                      >
                        {comp.domain}
                      </a>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {comp.products?.length || 0} товаров • {comp.competitor_type}
                        {comp.last_price_update && (
                          <span className="ml-2 text-xs">
                            Цены актуальны на {new Date(comp.last_price_update).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' })} {new Date(comp.last_price_update).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })} (UTC)
                          </span>
                        )}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Link to={`/analysis/${id}/competitor/${comp.id}/selectors`} className="btn-secondary text-sm flex items-center space-x-2">
                      <Settings className="h-4 w-4" />
                      <span>Настроить</span>
                    </Link>
                    {!isDemo && comp.products?.length > 0 && (
                      <button
                        onClick={() => handleUpdatePrices(comp.id)}
                        disabled={isUpdatingPrices}
                        className="btn-secondary text-sm flex items-center space-x-2"
                      >
                        <RefreshCw className={`h-4 w-4 ${isUpdatingPrices ? 'animate-spin' : ''}`} />
                        <span>Обновить</span>
                      </button>
                    )}
                  </div>
                </div>
                {comp.products?.length > 0 ? (
                  <div className="space-y-2 max-h-96 overflow-y-auto">
                    {comp.products.map(product => (
                      <div key={product.id} className="p-3 bg-gray-50 dark:bg-gray-800 rounded-lg border-b border-gray-200 dark:border-gray-700">
                        <p className="font-medium text-gray-900 dark:text-gray-100">{product.name}</p>
                        <div className="flex items-center space-x-4 mt-1">
                          <p className="text-gray-600 dark:text-gray-400">{formatPrice(product.price)}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8">
                    <p className="text-gray-500 dark:text-gray-400">Нет товаров. Настройте селекторы</p>
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

      {/* Edit Domain and Selectors Modal */}
      {showEditDomainModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg max-w-md w-full p-6">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
              Редактирование домена и селекторов
            </h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Домен (URL каталога)
                </label>
                <input
                  type="text"
                  value={editingDomain}
                  onChange={(e) => setEditingDomain(e.target.value)}
                  className="input-field w-full"
                  placeholder="example.ru/catalog"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Селектор названия товара
                </label>
                <input
                  type="text"
                  value={editingTitleSelector}
                  onChange={(e) => setEditingTitleSelector(e.target.value)}
                  className="input-field w-full font-mono text-sm"
                  placeholder=".product-title"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  Селектор цены
                </label>
                <input
                  type="text"
                  value={editingPriceSelector}
                  onChange={(e) => setEditingPriceSelector(e.target.value)}
                  className="input-field w-full font-mono text-sm"
                  placeholder=".product-price"
                />
              </div>
            </div>

            <div className="flex justify-end space-x-2 mt-6">
              <button
                onClick={() => setShowEditDomainModal(false)}
                className="btn-secondary text-sm"
              >
                Отмена
              </button>
              <button
                onClick={handleSaveDomainAndSelectors}
                className="btn-primary text-sm"
              >
                Сохранить
              </button>
            </div>
          </div>
        </div>
      )}

      {/* How It Works Modal */}
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
                  <span className="text-primary-600 dark:text-primary-400 font-semibold text-sm">1</span>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white mb-1">Выберите ваш товар</h4>
                  <p className="text-sm">В левой колонке отображаются товары с вашего сайта. Кликните на товар, чтобы выбрать его для связывания.</p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-primary-100 dark:bg-primary-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-primary-600 dark:text-primary-400 font-semibold text-sm">2</span>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white mb-1">Выберите товар конкурента</h4>
                  <p className="text-sm">В правой колонке отображаются товары конкурентов. Выберите аналогичный товар того же конкурента для создания связи.</p>
                </div>
              </div>

              <div className="flex items-start space-x-3">
                <div className="w-8 h-8 bg-primary-100 dark:bg-primary-900 rounded-full flex items-center justify-center flex-shrink-0">
                  <span className="text-primary-600 dark:text-primary-400 font-semibold text-sm">3</span>
                </div>
                <div>
                  <h4 className="font-medium text-gray-900 dark:text-white mb-1">Свяжите товары</h4>
                  <p className="text-sm">После выбора обоих товаров нажмите кнопку "Связать", чтобы создать связь между ними. Эта связь будет использоваться для сравнения цен в отчёте.</p>
                </div>
              </div>

              <div className="mt-6 p-4 bg-blue-50 dark:bg-blue-900/30 rounded-lg">
                <h4 className="font-medium text-blue-900 dark:text-blue-100 mb-2">Важно:</h4>
                <ul className="text-sm space-y-1 text-blue-800 dark:text-blue-200">
                  <li>• Один товар с вашего сайта можно связать только с одним товаром конкурента</li>
                  <li>• Связи используются для формирования отчёта по сравнению цен</li>
                  <li>• Вы можете удалить связь в любое время, нажав на значок корзины в таблице "Текущие связи"</li>
                </ul>
              </div>
            </div>

            <div className="flex justify-end mt-6">
              <button
                onClick={() => setShowHowItWorksModal(false)}
                className="btn-primary"
              >
                Понятно
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}