import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  LineElement,
  PointElement
} from 'chart.js'
import { Bar, Doughnut, Line } from 'react-chartjs-2'

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  Title,
  Tooltip,
  Legend,
  ArcElement,
  LineElement,
  PointElement
)

export function PriceComparisonChart({ data }) {
  const chartData = {
    labels: data?.map(d => d.competitor?.substring(0, 15) || 'Unknown') || [],
    datasets: [
      {
        label: 'Ваша цена',
        data: data?.map(d => d.user_price) || [],
        backgroundColor: 'rgba(59, 130, 246, 0.8)',
        borderColor: 'rgb(59, 130, 246)',
        borderWidth: 1
      },
      {
        label: 'Цена конкурента',
        data: data?.map(d => d.competitor_price) || [],
        backgroundColor: 'rgba(239, 68, 68, 0.8)',
        borderColor: 'rgb(239, 68, 68)',
        borderWidth: 1
      }
    ]
  }

  const options = {
    responsive: true,
    plugins: {
      legend: { position: 'top' },
      title: { display: true, text: 'Сравнение цен' }
    },
    scales: {
      y: { beginAtZero: true, title: { display: true, text: 'Цена (₽)' } }
    }
  }

  return <Bar data={chartData} options={options} />
}

export function PriceDifferenceChart({ data }) {
  const chartData = {
    labels: data?.map(d => d.competitor_product?.substring(0, 15) || 'Product') || [],
    datasets: [
      {
        label: 'Разница в цене (₽)',
        data: data?.map(d => d.price_difference) || [],
        backgroundColor: data?.map(d => 
          d.price_difference > 0 ? 'rgba(239, 68, 68, 0.7)' : 
          d.price_difference < 0 ? 'rgba(34, 197, 94, 0.7)' : 
          'rgba(156, 163, 175, 0.7)'
        ) || [],
        borderWidth: 1
      }
    ]
  }

  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      title: { display: true, text: 'Разница цен' }
    },
    scales: {
      y: { 
        beginAtZero: true,
        title: { display: true, text: 'Разница (₽)' }
      }
    }
  }

  return <Bar data={chartData} options={options} />
}

export function CompetitorsDistribution({ competitors }) {
  const counts = {}
  competitors?.forEach(c => {
    const type = c.competitor_type || 'unknown'
    counts[type] = (counts[type] || 0) + 1
  })

  const chartData = {
    labels: Object.keys(counts),
    datasets: [{
      data: Object.values(counts),
      backgroundColor: [
        'rgba(59, 130, 246, 0.8)',
        'rgba(239, 68, 68, 0.8)',
        'rgba(34, 197, 94, 0.8)',
        'rgba(234, 179, 8, 0.8)'
      ],
      borderWidth: 1
    }]
  }

  const options = {
    responsive: true,
    plugins: {
      legend: { position: 'right' },
      title: { display: true, text: 'Типы конкурентов' }
    }
  }

  return <Doughnut data={chartData} options={options} />
}

export function AnalysisHistoryChart({ analyses }) {
  const last7Days = []
  const counts = {}
  
  for (let i = 6; i >= 0; i--) {
    const date = new Date()
    date.setDate(date.getDate() - i)
    const key = date.toISOString().split('T')[0]
    last7Days.push(key)
    counts[key] = 0
  }

  analyses?.forEach(a => {
    const key = a.created_at?.split('T')[0]
    if (counts[key] !== undefined) counts[key]++
  })

  const chartData = {
    labels: last7Days.map(d => {
      const date = new Date(d)
      return date.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
    }),
    datasets: [{
      label: 'Анализов',
      data: last7Days.map(d => counts[d]),
      borderColor: 'rgb(59, 130, 246)',
      backgroundColor: 'rgba(59, 130, 246, 0.1)',
      fill: true,
      tension: 0.3
    }]
  }

  const options = {
    responsive: true,
    plugins: {
      legend: { display: false },
      title: { display: true, text: 'История анализов (7 дней)' }
    },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } }
    }
  }

  return <Line data={chartData} options={options} />
}
