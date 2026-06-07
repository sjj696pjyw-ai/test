/**
 * Исправляет проблему с кодировкой UTF-8, когда текст отображается как "Ð¡Ð¼Ð°ÑÑÑÐ¾Ð½"
 * вместо "Смартфон". Это происходит из-за двойного кодирования UTF-8.
 * 
 * @param {string} str - Строка с возможной проблемой кодировки
 * @returns {string} - Исправленная строка или оригинал, если исправление невозможно
 */
export function fixEncoding(str) {
    if (!str || typeof str !== 'string') return str;

    try {
        // Проверяем, содержит ли строка символы, характерные для проблемы кодировки
        // Если строка содержит последовательности вроде "Ð", "Ñ", "Ï", это признак проблемы
        const hasEncodingIssue = /[ÐÑÏÒÓÔÕÖØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõöøùúûüýþÿ]/.test(str);
        
        if (!hasEncodingIssue) {
            return str; // Нет признаков проблемы, возвращаем как есть
        }

        // Преобразуем строку в байты (как если бы она была в Latin1/Windows-1252)
        // и затем интерпретируем эти байты как UTF-8
        const bytes = new Uint8Array(str.split('').map(char => char.charCodeAt(0)));
        const decoded = new TextDecoder('utf-8').decode(bytes);

        // Проверяем, содержит ли результат символы замены (ошибка декодирования)
        if (decoded.includes('\uFFFD')) {
            return str; // Возвращаем оригинал, если не удалось исправить
        }

        return decoded;
    } catch (e) {
        console.warn('Не удалось исправить кодировку:', e);
        return str;
    }
}

/**
 * Применяет fixEncoding к объекту, рекурсивно обрабатывая все строковые поля
 * @param {any} data - Данные для обработки
 * @returns {any} - Обработанные данные
 */
export function fixEncodingRecursive(data) {
    if (typeof data === 'string') {
        return fixEncoding(data);
    }
    
    if (Array.isArray(data)) {
        return data.map(item => fixEncodingRecursive(item));
    }
    
    if (data !== null && typeof data === 'object') {
        const result = {};
        for (const [key, value] of Object.entries(data)) {
            result[key] = fixEncodingRecursive(value);
        }
        return result;
    }
    
    return data;
}
