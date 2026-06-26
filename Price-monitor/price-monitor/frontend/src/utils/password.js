// Единая политика паролей (должна совпадать с бэкендом: backend/app/routes/auth.py).
// Требования: не менее PASSWORD_MIN символов, хотя бы одна буква и хотя бы одна цифра.

export const PASSWORD_MIN = 8

/** Возвращает текст ошибки или '' (пустую строку), если пароль валиден. */
export function passwordError(pw) {
  if (pw.length < PASSWORD_MIN) return `Пароль должен быть не менее ${PASSWORD_MIN} символов`
  if (!/[A-Za-zА-Яа-яЁё]/.test(pw)) return 'Добавьте хотя бы одну букву'
  if (!/\d/.test(pw)) return 'Добавьте хотя бы одну цифру'
  return ''
}

/** Грубая оценка надёжности: 0..4 (для индикатора). */
export function passwordScore(pw) {
  if (!pw) return 0
  let s = 0
  if (pw.length >= PASSWORD_MIN) s++
  if (pw.length >= 12) s++
  if (/[a-zа-яё]/.test(pw) && /[A-ZА-ЯЁ]/.test(pw)) s++ // буквы разного регистра
  if (/\d/.test(pw)) s++
  if (/[^A-Za-zА-Яа-яЁё0-9]/.test(pw)) s++ // спецсимвол
  return Math.min(4, s)
}

/** Метка и цвет для индикатора надёжности. */
export function passwordStrength(pw) {
  const score = passwordScore(pw)
  const labels = ['', 'Слабый', 'Средний', 'Хороший', 'Надёжный']
  const colors = ['bg-gray-300', 'bg-red-500', 'bg-yellow-500', 'bg-blue-500', 'bg-green-500']
  return { score, label: labels[score], color: colors[score] }
}
