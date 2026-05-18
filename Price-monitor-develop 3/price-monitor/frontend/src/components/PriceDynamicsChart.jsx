import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export function PriceDynamicsChart({ data, dateRange }) {
  if (!data || data.length === 0) {
    return (
      <div className="text-center py-8 text-gray-500 dark:text-gray-400">
        Нет данных для отображения графика
      </div>
    )
  }
  
  // Transform data for Recharts format
  const chartData = []
  const productLegends = []
  const seenProducts = new Set()
  const allDates = new Set()

  // Collect all unique dates and build series
  data.forEach((series, index) => {
    const userColor = '#22c55e' // green-500
    const competitorColor = '#3b82f6' // blue-500
    
    // Add user product only once (avoid duplicates by name only)
    const userKey = `user_${series.product_name}`
    if (!seenProducts.has(userKey)) {
      seenProducts.add(userKey)
      productLegends.push({
        name: `Мой: ${series.product_name}`,
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
      let existingPoint = chartData.find(d => d.date === point.date)
      if (!existingPoint) {
        existingPoint = { date: point.date }
        chartData.push(existingPoint)
      }
      
      // Store price with the specific index to keep series separate
      if (point.user_price !== null && point.user_price !== undefined) {
        existingPoint[`user_${index}`] = point.user_price
      }
      if (point.competitor_price !== null && point.competitor_price !== undefined) {
        existingPoint[`competitor_${index}`] = point.competitor_price
      }
    })
  })

  // If dateRange is provided, add all dates from the range
  if (dateRange && dateRange.start && dateRange.end) {
    const startDate = new Date(dateRange.start)
    const endDate = new Date(dateRange.end)
    const currentDate = new Date(startDate)
    
    while (currentDate <= endDate) {
      const dateStr = currentDate.toISOString().split('T')[0]
      allDates.add(dateStr)
      currentDate.setDate(currentDate.getDate() + 1)
    }
  }

  // Create complete date range with all dates (even those without data)
  const sortedDates = Array.from(allDates).sort((a, b) => new Date(a) - new Date(b))
  const completeChartData = sortedDates.map(date => {
    const existingPoint = chartData.find(d => d.date === date)
    if (existingPoint) {
      return existingPoint
    }
    return { date }
  })

  // Sort by date
  completeChartData.sort((a, b) => new Date(a.date) - new Date(b.date))
  
  // Use completeChartData as display data (keep chronological order)
  const displayChartData = completeChartData

  // Calculate min and max prices for dynamic Y-axis domain
  let minPrice = Infinity
  let maxPrice = -Infinity
  displayChartData.forEach(point => {
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
    if (active && payload && payload.length) {
      // Filter to show only entries that have a value at this specific point
      // and deduplicate by product name + site domain
      const seenProducts = new Set()
      const validEntries = payload
        .filter(entry => entry.value !== null && entry.value !== undefined)
        .filter(entry => {
          // Create unique key from product name and color (to distinguish same products on different sites)
          const productKey = `${entry.name}-${entry.color}`
          if (seenProducts.has(productKey)) {
            return false
          }
          seenProducts.add(productKey)
          return true
        })
      
      if (validEntries.length === 0) return null
      
      return (
        <div className="bg-white dark:bg-gray-800 p-3 border border-gray-200 dark:border-gray-700 rounded shadow-lg">
          <p className="font-medium mb-2 text-gray-900 dark:text-gray-100">{formatDate(label)}</p>
          {validEntries.map((entry, idx) => (
            <div key={idx} className="flex items-center gap-2 text-sm">
              <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }}></div>
              <span className="text-gray-600 dark:text-gray-400">{entry.name}:</span>
              <span className="font-semibold text-gray-900 dark:text-gray-100">
                {`${Math.round(entry.value)} ₽`}
              </span>
            </div>
          ))}
        </div>
      )
    }
    return null
  }

  const CustomLegend = ({ payload }) => {
    return (
      <div className="flex flex-wrap justify-center gap-4 mt-4">
        {productLegends.map((legend, idx) => (
          <div 
            key={idx} 
            className={`flex items-center gap-2 transition-opacity ${legend.url ? 'cursor-pointer hover:opacity-75' : ''}`}
            title={legend.url ? 'Перейти к товару' : ''}
            onClick={() => {
              if (legend.url) {
                window.open(legend.url, '_blank')
              }
            }}
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

  // Build line elements dynamically
  const lines = []
  data.forEach((series, index) => {
    const userColor = '#22c55e'
    const competitorColor = '#3b82f6'
    
    lines.push(
      <Line
        key={`user_${index}`}
        type="monotone"
        dataKey={`user_${index}`}
        stroke={userColor}
        strokeWidth={2}
        dot={{ r: 4 }}
        name={`Мой: ${series.product_name}`}
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
        dot={{ r: 4 }}
        name={`${series.competitor_name} (${series.competitor_domain})`}
        connectNulls={false}
      />
    )
  })

  return (
    <div className="space-y-4">
      <div className="h-[500px] pt-8 overflow-visible">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={displayChartData} margin={{ top: 20, right: 30, left: 60, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
            <XAxis 
              dataKey="date" 
              tickFormatter={formatDate}
              className="text-xs text-gray-500 dark:text-gray-400"
              interval={0}
              angle={-45}
              textAnchor="end"
              height={60}
              tick={{ fill: 'currentColor' }}
              type="category"
              scale="point"
            />
            <YAxis 
              className="text-xs text-gray-500 dark:text-gray-400"
              tickFormatter={(value) => `${Math.round(value)} ₽`}
              domain={yAxisDomain}
              width={80}
              tick={{ fill: 'currentColor' }}
            />
            <Tooltip content={<CustomTooltip />} cursor={false} />
            <Legend content={<CustomLegend />} />
            {lines}
          </LineChart>
        </ResponsiveContainer>
      </div>
      <p className="text-xs text-gray-500 dark:text-gray-400 text-center">
        Нажмите на название товара в легенде для перехода на сайт
      </p>
    </div>
  )
}
