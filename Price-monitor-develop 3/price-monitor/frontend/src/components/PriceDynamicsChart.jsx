import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'
import { useState, useMemo, useEffect } from 'react'

// «Круглые» границы и метки для оси цен (например 92000, 96000, 100000, ...)
function niceScale(min, max, tickCount = 5) {
  if (!isFinite(min) || !isFinite(max) || min === max) {
    const base = isFinite(min) ? min : 0
    min = base - 1000
    max = base + 1000
  }
  const niceNum = (range, round) => {
    const exp = Math.floor(Math.log10(range))
    const f = range / Math.pow(10, exp)
    let nf
    if (round) nf = f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10
    else nf = f <= 1 ? 1 : f <= 2 ? 2 : f <= 5 ? 5 : 10
    return nf * Math.pow(10, exp)
  }
  const range = niceNum(max - min, false)
  const step = niceNum(range / (tickCount - 1), true)
  const niceMin = Math.floor(min / step) * step
  const niceMax = Math.ceil(max / step) * step
  const ticks = []
  for (let v = niceMin; v <= niceMax + step * 0.5; v += step) ticks.push(Math.round(v))
  // Отступ сверху/снизу (полшага), чтобы крайние точки не обрезались о границу.
  // Метки остаются «круглыми» (домен шире, чем диапазон меток).
  const pad = step * 0.5
  return { domain: [niceMin - pad, niceMax + pad], ticks }
}

// Кастомная стрелка для select, чтобы она не прилипала к краю
const SELECT_CHEVRON = {
  appearance: 'none',
  backgroundImage: 'url("data:image/svg+xml,%3Csvg xmlns=\'http://www.w3.org/2000/svg\' width=\'16\' height=\'16\' viewBox=\'0 0 24 24\' fill=\'none\' stroke=\'%239ca3af\' stroke-width=\'2\' stroke-linecap=\'round\' stroke-linejoin=\'round\'%3E%3Cpolyline points=\'6 9 12 15 18 9\'/%3E%3C/svg%3E")',
  backgroundRepeat: 'no-repeat',
  backgroundPosition: 'right 0.6rem center',
  backgroundSize: '1rem'
}

export function PriceDynamicsChart({ data, dateRange, selectedUserProductId, onFilterChange, userProducts, title }) {
  const [activeDot, setActiveDot] = useState(null)
  const [filterProduct, setFilterProduct] = useState(selectedUserProductId || null)
  const [highlightedLegend, setHighlightedLegend] = useState(null)
  // Свободный фильтр по датам (в пределах доступных данных)
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')

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

  // Пока товар не выбран — данных нет, график не строится
  const filteredData = useMemo(() => {
    if (!filterProduct) {
      return []
    }
    return data.filter(series => {
      return series.user_product_id === filterProduct
    })
  }, [data, filterProduct])

  // Границы доступных дат (по всем товарам) — для ограничений выбора дат
  const dataBounds = useMemo(() => {
    let min = null, max = null
    data.forEach(s => (s.data_points || []).forEach(p => {
      if (!min || p.date < min) min = p.date
      if (!max || p.date > max) max = p.date
    }))
    const today = new Date().toISOString().split('T')[0]
    if (!max || today > max) max = today
    if (!min) min = today
    return { min, max }
  }, [data])

  // Handle filter change
  const handleFilterChange = (productId) => {
    const newFilter = productId ? Number(productId) : null
    setFilterProduct(newFilter)
    if (onFilterChange) {
      onFilterChange(newFilter)
    }
  }

  // Если товар всего один — сразу выбираем его (без шага «Выберите товар»)
  useEffect(() => {
    if (!filterProduct && availableUserProducts.length === 1) {
      handleFilterChange(availableUserProducts[0].id)
    }
  }, [availableUserProducts, filterProduct])

  // Transform data for Recharts format - connect all points without gaps
  const productLegends = []
  const seenProducts = new Set()
  const allDates = new Set()

  // Collect all unique dates from actual data points (not generating full date range)
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
        dataKey: `user_${index}`,
        seriesIndex: index
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
        dataKey: `competitor_${index}`,
        seriesIndex: index
      })
    }

    series.data_points.forEach(point => {
      allDates.add(point.date)
    })
  })

  // Sort dates chronologically
  const sortedDates = Array.from(allDates).sort()

  // Эффективные границы выбранного диапазона дат
  const effStart = startDate || dataBounds.min
  const effEnd = endDate || dataBounds.max

  // Строим непрерывный диапазон дней от effStart до effEnd.
  // realKeys — множество ключей `${dataKey}__${date}`, где есть РЕАЛЬНАЯ точка
  // (для отрисовки кружков). Граничные значения интерполируются без кружка.
  const { chartData, realKeys } = useMemo(() => {
    if (!filterProduct || filteredData.length === 0) {
      return { chartData: [], realKeys: new Set() }
    }

    const rangeSet = new Set()
    const cursor = new Date(effStart + 'T00:00:00Z')
    const last = new Date(effEnd + 'T00:00:00Z')
    while (cursor <= last) {
      rangeSet.add(cursor.toISOString().split('T')[0])
      cursor.setUTCDate(cursor.getUTCDate() + 1)
    }
    sortedDates.forEach(ds => {
      if (ds >= effStart && ds <= effEnd) rangeSet.add(ds)
    })
    const visibleDates = Array.from(rangeSet).sort()

    const realKeys = new Set()
    const byDate = new Map(visibleDates.map(d => [d, { date: d }]))
    const ms = (d) => new Date(d + 'T00:00:00Z').getTime()

    filteredData.forEach((series, index) => {
      const pts = [...series.data_points].sort((a, b) => (a.date < b.date ? -1 : 1))
      ;[['user', 'user_price'], ['competitor', 'competitor_price']].forEach(([kind, field]) => {
        const key = `${kind}_${index}`
        const valued = pts.filter(p => p[field] !== null && p[field] !== undefined)

        // Реальные точки внутри диапазона — с кружком
        valued.forEach(p => {
          if (p.date >= effStart && p.date <= effEnd && byDate.has(p.date)) {
            byDate.get(p.date)[key] = p[field]
            realKeys.add(`${key}__${p.date}`)
          }
        })

        // Продление линии к ПРАВОЙ границе в сторону точки за фильтром (без кружка)
        const lastIn = [...valued].reverse().find(p => p.date <= effEnd)
        const nextOut = valued.find(p => p.date > effEnd)
        if (lastIn && nextOut && lastIn.date < effEnd && byDate.get(effEnd)[key] === undefined) {
          const t = (ms(effEnd) - ms(lastIn.date)) / (ms(nextOut.date) - ms(lastIn.date))
          byDate.get(effEnd)[key] = lastIn[field] + (nextOut[field] - lastIn[field]) * t
        }

        // Продление линии к ЛЕВОЙ границе в сторону точки до фильтра (без кружка)
        const firstIn = valued.find(p => p.date >= effStart)
        const prevOut = [...valued].reverse().find(p => p.date < effStart)
        if (firstIn && prevOut && firstIn.date > effStart && byDate.get(effStart)[key] === undefined) {
          const t = (ms(effStart) - ms(prevOut.date)) / (ms(firstIn.date) - ms(prevOut.date))
          byDate.get(effStart)[key] = prevOut[field] + (firstIn[field] - prevOut[field]) * t
        }
      })
    })

    return { chartData: visibleDates.map(d => byDate.get(d)), realKeys }
  }, [filterProduct, filteredData, sortedDates, effStart, effEnd])

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

  // «Круглые» границы и метки оси цен (относительно цены товара)
  const { domain: yAxisDomain, ticks: yTicks } = niceScale(minPrice, maxPrice)

  // Адаптивный интервал подписей оси X, чтобы метки не наслаивались
  const xTickInterval = chartData.length <= 14
    ? 0
    : Math.ceil(chartData.length / 12) - 1

  // Format date for display
  const formatDate = (dateStr) => {
    const date = new Date(dateStr)
    return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
  }

  const CustomTooltip = ({ payload, label }) => {
    // Тултип показывается только при наведении на конкретную точку
    if (!activeDot) return null

    // Показываем товары, находящиеся в этой же точке: та же дата и та же цена.
    // Свой товар может встречаться в нескольких сериях — дедупим по названию.
    let items = []
    if (payload && payload.length) {
      const seenNames = new Set()
      items = payload.filter(p => {
        if (p.value === null || p.value === undefined) return false
        if (p.value !== activeDot.value) return false
        if (seenNames.has(p.name)) return false
        seenNames.add(p.name)
        return true
      })
    }

    // Запасной вариант (например, у крайней правой точки, где payload пуст) —
    // показываем хотя бы наведённый товар, чтобы тултип не пропадал.
    if (!items.length) {
      items = [{ name: activeDot.name, value: activeDot.value, color: activeDot.color }]
    }

    const labelDate = label ?? (activeDot.index != null ? chartData[activeDot.index]?.date : null)

    return (
      <div className="bg-white dark:bg-gray-800 p-3 border border-gray-200 dark:border-gray-700 rounded shadow-lg">
        {labelDate && <p className="font-medium mb-2 text-gray-900 dark:text-gray-100">{formatDate(labelDate)}</p>}
        <div className="space-y-1">
          {items.map((item, idx) => (
            <div key={idx} className="flex items-center gap-2 text-sm">
              <div className="w-3 h-3 rounded-full shrink-0" style={{ backgroundColor: item.color || item.stroke }}></div>
              <span className="text-gray-600 dark:text-gray-400 truncate max-w-[220px]">{item.name}:</span>
              <span className="font-semibold text-gray-900 dark:text-gray-100 ml-auto">
                {`${Math.round(item.value)} ₽`}
              </span>
            </div>
          ))}
        </div>
      </div>
    )
  }

  const CustomLegend = ({ payload }) => {
    return (
      <div
        className="flex flex-wrap justify-center gap-4 mt-4"
        onMouseLeave={() => setHighlightedLegend(null)}
      >
        {productLegends.map((legend, idx) => (
          <div
            key={idx}
            title={legend.name}
            className={`flex items-center gap-2 transition-opacity cursor-pointer ${
              highlightedLegend !== null && highlightedLegend !== legend.dataKey ? 'opacity-40' : 'opacity-100'
            }`}
            onMouseEnter={() => setHighlightedLegend(legend.dataKey)}
          >
            <div
              className={`w-3 h-3 rounded-full ${
                highlightedLegend === legend.dataKey ? 'ring-2 ring-offset-2 dark:ring-offset-gray-900' : ''
              }`}
              style={{ 
                backgroundColor: legend.color,
                boxShadow: highlightedLegend === legend.dataKey ? `0 0 8px ${legend.color}` : 'none',
                ringColor: legend.color
              }}
            ></div>
            <span className={`text-sm text-gray-700 dark:text-gray-300 max-w-xs truncate ${
              highlightedLegend === legend.dataKey ? 'font-semibold' : ''
            }`}>
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

    // Кружок рисуем только для реальных точек; для интерполированных
    // граничных значений (продление линии за фильтр) кружок не нужен.
    if (payload?.date && !realKeys.has(`${dataKey}__${payload.date}`)) {
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
    
    // Check if this dot should be highlighted based on legend hover
    const isHighlightedByLegend = highlightedLegend !== null && highlightedLegend === dataKey

    return (
      <circle
        cx={cx}
        cy={cy}
        r={isHovered || isHighlightedByLegend ? 8 : 4}
        fill={fill}
        stroke={stroke}
        strokeWidth={isHovered || isHighlightedByLegend ? 3 : 2}
        style={{ 
          cursor: 'pointer',
          filter: isHighlightedByLegend ? `drop-shadow(0 0 4px ${fill})` : 'none'
        }}
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
        strokeWidth={highlightedLegend === `user_${index}` ? 4 : 2}
        dot={(props) => <CustomDot {...props} />}
        activeDot={false}
        name={`${series.product_name}`}
        connectNulls={true}
        isAnimationActive={false}
      />
    )

    lines.push(
      <Line
        key={`competitor_${index}`}
        type="monotone"
        dataKey={`competitor_${index}`}
        stroke={competitorColor}
        strokeWidth={highlightedLegend === `competitor_${index}` ? 4 : 2}
        dot={(props) => <CustomDot {...props} />}
        activeDot={false}
        name={`${series.competitor_name} (${series.competitor_domain})`}
        connectNulls={true}
        isAnimationActive={false}
      />
    )
  })

  // Линию наведённого товара выводим поверх остальных (для совпадающих динамик)
  const orderedLines = highlightedLegend
    ? [...lines.filter(l => l.key !== highlightedLegend), ...lines.filter(l => l.key === highlightedLegend)]
    : lines

  return (
    <div className="space-y-4">
      {/* Заголовок + фильтры в одной строке */}
      <div className="flex items-center justify-between gap-4 flex-wrap">
        {title && (
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{title}</h3>
        )}
        <div className="flex items-center gap-4 flex-wrap ml-auto">
        {availableUserProducts.length > 0 && (
          <div className="flex items-center gap-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Фильтр по товарам:
            </label>
            <select
              value={filterProduct || ''}
              onChange={(e) => handleFilterChange(e.target.value)}
              style={SELECT_CHEVRON}
              className="text-sm border border-gray-300 dark:border-gray-600 rounded pl-2 pr-9 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500"
            >
              {availableUserProducts.length !== 1 && <option value="">Выберите товар</option>}
              {availableUserProducts.map(product => (
                <option key={product.id} value={product.id}>
                  {product.name}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Период:
          </label>
          <input
            type="date"
            value={effStart}
            min={dataBounds.min}
            max={effEnd}
            onChange={(e) => setStartDate(e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 [color-scheme:light] dark:[color-scheme:dark]"
          />
          <span className="text-gray-400">—</span>
          <input
            type="date"
            value={effEnd}
            min={effStart}
            max={dataBounds.max}
            onChange={(e) => setEndDate(e.target.value)}
            className="text-sm border border-gray-300 dark:border-gray-600 rounded px-2 py-1 bg-white dark:bg-gray-800 text-gray-900 dark:text-gray-100 focus:outline-none focus:ring-2 focus:ring-primary-500 [color-scheme:light] dark:[color-scheme:dark]"
          />
        </div>
        </div>
      </div>

      {!filterProduct ? (
        <div className="h-40 flex items-center justify-center text-gray-500 dark:text-gray-400">
          Выберите товар, чтобы построить график
        </div>
      ) : (
        <div className="h-[500px] pt-8 overflow-visible">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={chartData} margin={{ top: 0, right: 30, left: 10, bottom: 20 }}>
              <CartesianGrid strokeDasharray="3 3" className="stroke-gray-200 dark:stroke-gray-700" />
              <XAxis
                dataKey="date"
                tickFormatter={formatDate}
                className="text-xs text-gray-500 dark:text-gray-400"
                interval={xTickInterval}
                angle={0}
                textAnchor="middle"
                height={50}
                tick={{ fill: 'currentColor', dy: 10 }}
                type="category"
                scale="point"
                padding={{ left: 15, right: 25 }}
                allowDataOverflow={false}
              />
              <YAxis
                className="text-xs text-gray-500 dark:text-gray-400"
                tickFormatter={(value) => `${Math.round(value).toLocaleString('ru-RU')} ₽`}
                domain={yAxisDomain}
                ticks={yTicks}
                allowDecimals={false}
                width={100}
                tick={{ fill: 'currentColor' }}
              />
              <Tooltip
                content={<CustomTooltip />}
                cursor={false}
                isAnimationActive={false}
                active={!!activeDot}
                allowEscapeViewBox={{ x: true, y: true }}
              />
              <Legend content={<CustomLegend />} />
              {orderedLines}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  )
}
