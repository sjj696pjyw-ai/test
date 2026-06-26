import { BarChart3 } from 'lucide-react'

// Аватар пользователя — фирменный кружок с логотипом сайта (BarChart).
// size — диаметр в пикселях (через inline-style, чтобы не зависеть от Tailwind-пурджа).
export default function Avatar({ size = 32, className = '' }) {
  return (
    <span
      className={`inline-flex items-center justify-center rounded-full bg-primary-600 text-white shrink-0 ${className}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <BarChart3 style={{ width: Math.round(size * 0.55), height: Math.round(size * 0.55) }} />
    </span>
  )
}
