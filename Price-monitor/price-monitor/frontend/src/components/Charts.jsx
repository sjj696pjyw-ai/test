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
import { Line } from 'react-chartjs-2'

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
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false }
    },
    scales: {
      y: { beginAtZero: true, ticks: { stepSize: 1 } }
    }
  }

  return <div className="h-full"><Line data={chartData} options={options} /></div>
}
