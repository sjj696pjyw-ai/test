import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

export function PriceDynamicsChart({ data }) {
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

  // Collect all unique dates and build series
  data.forEach((series, index) => {
    const userColor = '#22c55e' // green-500
    const competitorColor = '#3b82f6' // blue-500
    
    productLegends.push({
      name: `Мой: ${series.product_name}`,
      type: 'user',
      color: userColor,
      url: series.product_url
    })
    
    productLegends.push({
      name: `${series.competitor_name} (${series.competitor_domain})`,
      type: 'competitor',
      color: competitorColor,
      url: series.product_url
    })

    series.data_points.forEach(point => {
      let existingPoint = chartData.find(d => d.date === point.date)
      if (!existingPoint) {
        existingPoint = { date: point.date }
        chartData.push(existingPoint)
      }
      
      if (point.user_price !== null && point.user_price !== undefined) {
        existingPoint[`user_${index}`] = point.user_price
      }
      if (point.competitor_price !== null && point.competitor_price !== undefined) {
        existingPoint[`competitor_${index}`] = point.competitor_price
      }
    })
  })

  // Sort by date
  chartData.sort((a, b) => new Date(a.date) - new Date(b.date))

  // Format date for display
  const formatDate = (dateStr) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  }

  const CustomTooltip = ({ active, payload, label }) => {
    if (active && payload && payload.length) {
      return (
        <div className="bg-white dark:bg-gray-800 p-3 border border-gray-200 dark:border-gray-700 rounded shadow-lg">
          <p className="font-medium mb-2 text-gray-900 dark:text-gray-100">{formatDate(label)}</p>
          {payload.map((entry, idx) => {
            const legend = productLegends.find(l => l.name === entry.name)
            return (
              <div key={idx} className="flex items-center gap-2 text-sm">
                <div className="w-3 h-3 rounded-full" style={{ backgroundColor: entry.color }}></div>
                <span className="text-gray-600 dark:text-gray-400">{entry.name}:</span>
                <span className="font-semibold text-gray-900 dark:text-gray-100">
                  {entry.value ? `${entry.value.toFixed(0)} ₽` : '-'}
                </span>
              </div>
            )
          })}
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
            className="flex items-center gap-2 cursor-pointer hover:opacity-75 transition-opacity"
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
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
            <XAxis 
              dataKey="date" 
              tickFormatter={formatDate}
              className="text-xs text-gray-500 dark:text-gray-400"
            />
            <YAxis 
              className="text-xs text-gray-500 dark:text-gray-400"
              tickFormatter={(value) => `${value} ₽`}
            />
            <Tooltip content={<CustomTooltip />} />
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
