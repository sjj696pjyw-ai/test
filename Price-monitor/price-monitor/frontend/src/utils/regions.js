export const REGIONS = [
  { value: '213', label: 'Москва' },
  { value: '2', label: 'Санкт-Петербург' },
  { value: '54', label: 'Екатеринбург' },
  { value: '47', label: 'Новосибирск' },
  { value: '43', label: 'Краснодар' },
  { value: '120', label: 'Казань' },
  { value: '51', label: 'Самара' },
  { value: '24', label: 'Воронеж' },
  { value: '35', label: 'Нижний Новгород' },
  { value: '39', label: 'Ростов-на-Дону' },
  { value: '38', label: 'Волгоград' },
  { value: '59', label: 'Пермь' },
  { value: '28', label: 'Уфа' },
  { value: '48', label: 'Омск' },
  { value: '50', label: 'Челябинск' },
  { value: '64', label: 'Саратов' },
  { value: '189', label: 'Тюмень' },
  { value: '30', label: 'Красноярск' },
  { value: '66', label: 'Ижевск' },
  { value: '75', label: 'Ставрополь' },
  { value: '44', label: 'Сочи' },
  { value: '58', label: 'Пенза' },
  { value: '57', label: 'Оренбург' },
  { value: '192', label: 'Кемерово' },
  { value: '69', label: 'Томск' },
  { value: '68', label: 'Ульяновск' },
  { value: '22', label: 'Хабаровск' },
  { value: '26', label: 'Владивосток' },
  { value: '70', label: 'Тольятти' },
  { value: '49', label: 'Барнаул' },
]

export const REGION_MAP = Object.fromEntries(REGIONS.map(r => [r.value, r.label]))

export function getRegionName(code) {
  return REGION_MAP[code] || code
}
