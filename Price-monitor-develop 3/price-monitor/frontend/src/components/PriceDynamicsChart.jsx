import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { useState, useMemo } from 'react'

export function PriceDynamicsChart({ data, dateRange, selectedUserProductId, onFilterChange, userProducts }) {
  const [activeDot, setActiveDot] = useState(null)
  const [filterProduct, setFilterProduct] = useState(selectedUserProductId || null)

  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        Нет данных для отображения графика
      </div>
    )
  }

  // Get unique user products from data for the filter
  const availableUserProducts = useMemo(() => {
    const products = new Map()
    data.forEach(series => {
      if (series.user_product_id && series.product_name) {
        products.set(series.user_product_id, {
          id: series.user_product_id,
          name: series.product_name
        })
      }
    })
    return Array.from(products.values())
  }, [data])

  // Filter data based on selected user product
  const filteredData = useMemo(() => {
    if (!filterProduct) {
      return data
    }
    return data.filter(series => {
      return series.user_product_id === filterProduct
    })
  }, [data, filterProduct])

  // Handle filter change
  const handleFilterChange = (productId) => {
    const newFilter = productId === 'all' ? null : productId
    setFilterProduct(newFilter)
    if (onFilterChange) {
      onFilterChange(newFilter)
    }
  }

  // Transform data for Recharts format
  const productLegends = []
  const seenProducts = new Set()
  const allDates = new Set()

  // Collect all unique dates and build series
  filteredData.forEach((series, index) => {
    const userColor = '#22c55e' // green-500
    const competitorColor = '#3b82f6' // blue-500

    // Add user product only once (avoid duplicates by name only)
    const userKey = `user_${series.product_name}`
    if (!seenProducts.has(userKey)) {
      seenProducts.add(userKey)
      productLegends.push({
        name: `${series.product_name}`,
        type: 'user',
        color: userColor,
        url: series.product_url,
        dataKey: `user_${index}`
      })
    }

    // Add competitor product (unique by name + domain combination)
    const competitorKey = `competitor_${series.competitor_name}_${series.competitor_domain}`
    if (!seenProducts.has(competitorKey)) {
      seenProducts.add(competitorKey)
      productLegends.push({
        name: `${series.competitor_name} (${series.competitor_domain})`,
        type: 'competitor',
        color: competitorColor,
        url: series.product_url,
        dataKey: `competitor_${index}`
      })
    }

    series.data_points.forEach(point => {
      allDates.add(point.date)
    })
  })

  // Generate complete date range: 3 days before today, today in center, 3 days after
  const chartData = useMemo(() => {
    const today = new Date()
    today.setHours(0, 0, 0, 0)
    const todayStr = today.toISOString().split('T')[0]

    // Create 7-day range: 3 days before, today, 3 days after
    const startDate = new Date(today)
    startDate.setDate(startDate.getDate() - 3)

    const endDate = new Date(today)
    endDate.setDate(endDate.getDate() + 3)

    const dateRangeArray = []
    const currentDate = new Date(startDate)

    while (currentDate <= endDate) {
      const dateStr = currentDate.toISOString().split('T')[0]
      dateRangeArray.push(dateStr)
      currentDate.setDate(currentDate.getDate() + 1)
    }

    // Build chart data points
    const result = []
    dateRangeArray.forEach(date => {
      const point = { date }

      filteredData.forEach((series, index) => {
        const seriesPoint = series.data_points.find(p => p.date === date)
        if (seriesPoint) {
          if (seriesPoint.user_price !== null && seriesPoint.user_price !== undefined) {
            point[`user_${index}`] = seriesPoint.user_price
          }
          if (seriesPoint.competitor_price !== null && seriesPoint.competitor_price !== undefined) {
            point[`competitor_${index}`] = seriesPoint.competitor_price
          }
        }
      })

      result.push(point)
    })

    return result
  }, [filteredData])

  // Calculate min and max prices for dynamic Y-axis domain
  let minPrice = Infinity
  let maxPrice = -Infinity
  chartData.forEach(point => {
    Object.keys(point).forEach(key => {
      if (key !== 'date' && point[key] !== null && point[key] !== undefined) {
        minPrice = Math.min(minPrice, point[key])
        maxPrice = Math.max(maxPrice, point[key])
      }
    })
  })

  // Add padding to the domain (10% of range)
  const priceRange = maxPrice - minPrice
  const padding = priceRange * 0.1 || 1000 // fallback if all prices are the same
  const yAxisDomain = [
    Math.floor(minPrice - padding),
    Math.ceil(maxPrice + padding)
  ]

  // Format date for display
  const formatDate = (dateStr) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length && activeDot) {
      // Filter payload to show only the hovered item
      const hoveredPayload = payload.find(p => p.dataKey === activeDot.dataKey && p.value === activeDot.value)

      if (hoveredPayload) {
        return (
          <div className="bg-white dark:bg-gray-800 p-3 border border-gray-200 dark:border-gray-700 rounded shadow-lg">
            <p className="font-medium mb-2 text-gray-900 dark:text-gray-100">{formatDate(label)}</p>
            <div className="flex items-center gap-2 text-sm">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: activeDot.color }}></div>
              <span className="text-gray-600 dark:text-gray-400">{activeDot.name}:</span>
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                {`${Math.round(activeDot.value)} ₽`}
              </span>
            </div>
          </div>
        )
      }
    }
    return null
  }

  const CustomLegend = ({ payload }) => {
    return (
      <div className="flex flex-wrap justify-center gap-4 mt-4">
        {productLegends.map((legend, idx) => (
          <div
            key={idx}
            className="flex items-center gap-2 transition-opacity"
          >
            <div
              className="w-3 h-3 rounded-full"
              style={{ backgroundColor: legend.color }}
            ></div>
            <span className="text-sm text-gray-700 dark:text-gray-300 max-w-xs truncate">
              {legend.name}
            </span>
          </div>
        ))}
      </div>
    )
  }

  // Custom dot component
  const CustomDot = (props) => {
    const { cx, cy, fill, stroke, value, dataKey, index, payload } = props

    if (value === null || value === undefined || !cx || !cy) {
      return null
    }

    // Find the product name for this dot - use filteredData instead of data
    let productName = ''
    let productUrl = ''
    const seriesIndex = parseInt(dataKey.split('_')[1])
    if (filteredData && filteredData[seriesIndex]) {
      if (dataKey.startsWith('user_')) {
        productName = `${filteredData[seriesIndex].product_name}`
        productUrl = filteredData[seriesIndex].product_url || ''
      } else {
        productName = `${filteredData[seriesIndex].competitor_name} (${filteredData[seriesIndex].competitor_domain})`
        productUrl = filteredData[seriesIndex].product_url || ''
      }
    }

    const isHovered = activeDot &&
                      activeDot.dataKey === dataKey &&
                      activeDot.index === index

    return (
      <circle
        cx={cx}
        cy={cy}
        r={isHovered ? 6 : 4}
        fill={fill}
        stroke={stroke}
        strokeWidth={2}
        style={{ cursor: 'pointer' }}
        onMouseEnter={() => {
          setActiveDot({
            dataKey,
            index,
            name: productName,
            value,
            color: fill,
            url: productUrl
          })
        }}
        onMouseLeave={() => {
          setActiveDot(null)
        }}
        onClick={(e) => {
          e.stopPropagation()
          if (productUrl) {
            window.open(productUrl, '_blank')
          }
        }}
      />
    )
  }

  // Build line elements dynamically
  const lines = []
  filteredData.forEach((series, index) => {
    const userColor = '#22c55e'
    const competitorColor = '#3b82f6'

    lines.push(
      <Line
        key={`user_${index}`}
        type="monotone"
        dataKey={`user_${index}`}
        stroke={userColor}
        strokeWidth={2}
        dot={(props) => <CustomDot {...props} />}
        activeDot={false}
        name={`${series.product_name}`}
        connectNulls={false}
      />
    )

    lines.push(
      <Line
        key={`competitor_${index}`}
        type="monotone"
        dataKey={`competitor_${index}`}
        stroke={competitorColor}
        strokeWidth={2}
        dot={(props) => <CustomDot {...props} />}
        activeDot={false}
        name={`${series.competitor_name} (${series.competitor_domain})`}
        connectNulls={false}
      />
    )
  })

  return (
    <div className="space-y-4">
      {/* Filter section */}
      {availableUserProducts.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Фильтр по товарам:
          </label>
          <select
            value={filterProduct || 'all'}
            onChange={(e) => handleFilterChange(e.target.value === 'all' ? null : Number(e.target.value))}
            className="text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
          >
            <option value="all">Все товары</option>
            {availableUserProducts.map(product => (
              <option key={product.id} value={product.id}>
                {product.name}
              </option>
            ))}
          </select>
        </div>
      )}
      
      <div className="h-[500px] pt-8 overflow-visible flex justify-center">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData} margin={{ top: 20, right: 30, left: 100, bottom: 40 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
            <XAxis
              dataKey="date"
              tickFormatter={formatDate}
              className="text-xs text-gray-500 dark:text-gray-400"
              interval={0}
              angle={0}
              textAnchor="middle"
              height={50}
              tick={{ fill: 'currentColor' }}
              type="category"
              scale="point"
              padding={{ left: 0, right: 0 }}
              allowDataOverflow={false}
            />
            <YAxis
              className="text-xs text-gray-500 dark:text-gray-400"
              tickFormatter={(value) => `${Math.round(value)} ₽`}
              domain={yAxisDomain}
              width={100}
              tick={{ fill: 'currentColor' }}
            />
            <Tooltip content={<CustomTooltip />} cursor={false} />
            <Legend content={<CustomLegend />} />
            {lines}
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}
