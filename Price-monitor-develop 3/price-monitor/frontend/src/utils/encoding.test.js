/**
 * ТЕСТОВЫЙ ФАЙЛ для проверки исправления кодировки
 * 
 * Примеры использования функции fixEncoding:
 */

// Импортируем функцию (в реальном коде)
// import { fixEncoding } from './utils/encoding'

// ============================================
// ПРИМЕР 1: Простое использование
// ============================================
const brokenText = "Ð¡Ð¼Ð°ÑÑÑÐ¾Ð½ Apple iPhone 17 Pro 1024 ÐÐ ÑÐ¸Ð½Ð¸Ð¹";
const fixedText = fixEncoding(brokenText);
console.log('До:', brokenText);
console.log('После:', fixedText);
// Ожидаемый результат: "Смартфон Apple iPhone 17 Pro 1024 ГБ синий"

// ============================================
// ПРИМЕР 2: Если текст уже корректный
// ============================================
const goodText = "Apple iPhone 17 Pro, 256 ГБ, «глубокий синий» (eSIM)";
const stillGoodText = fixEncoding(goodText);
console.log('До:', goodText);
console.log('После:', stillGoodText);
// Результат: текст останется без изменений

// ============================================
// ПРИМЕР 3: Массовая обработка данных
// ============================================
const products = [
  { id: 1, name: "Ð¡Ð¼Ð°ÑÑÑÐ¾Ð½ iPhone 15", price: 89990 },
  { id: 2, name: "ÐÐ¾ÑÑÐ±ÑÐº MacBook Pro", price: 159990 },
  { id: 3, name: "Planшет iPad Air", price: 59990 } // уже корректно
];

const fixedProducts = products.map(p => ({
  ...p,
  name: fixEncoding(p.name)
}));

console.log('Исправленные товары:', fixedProducts);

// ============================================
// ПРИМЕР 4: Глубокая обработка объектов
// ============================================
const apiResponse = {
  analysis: {
    id: 1,
    competitors: [
      {
        domain: "example.ru",
        products: [
          { name: "Ð¢ÐµÐ»ÐµÑÐ¾Ð½ Samsung Galaxy", price: 79990 },
          { name: "ÐÐ»Ð°Ð½ÑÐµÑ iPad Pro", price: 99990 }
        ]
      }
    ]
  }
};

const fixedResponse = fixEncodingRecursive(apiResponse);
console.log('Исправленный ответ API:', fixedResponse);

// ============================================
// Где применять в коде:
// ============================================
/*
1. При получении текста из селекторов:
   const rawTitle = element.textContent.trim();
   const title = fixEncoding(rawTitle);

2. В интерцепторе axios (уже добавлено в api.js):
   - Все ответы от сервера автоматически обрабатываются
   
3. При отображении данных в UI:
   - Данные уже будут исправлены благодаря интерцептору
*/
