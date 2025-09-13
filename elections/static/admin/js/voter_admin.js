// JavaScript для настройки полей даты в админке избирателей

document.addEventListener('DOMContentLoaded', function() {
    // Функция для уменьшения ширины полей даты и колонок
    function resizeDateFields() {
        // Находим все поля даты более агрессивно
        const allInputs = document.querySelectorAll('input[type="text"]');
        
        allInputs.forEach(function(input) {
            const name = input.name || '';
            const id = input.id || '';
            
            // Проверяем, является ли поле полем даты
            if (name.includes('planned_date') || name.includes('voting_date') || 
                id.includes('planned_date') || id.includes('voting_date')) {
                
                // Применяем стили принудительно (100px для всех полей даты)
                input.style.setProperty('width', '100px', 'important');
                input.style.setProperty('max-width', '100px', 'important');
                input.style.setProperty('min-width', '100px', 'important');
                input.style.setProperty('box-sizing', 'border-box', 'important');
                input.setAttribute('size', '10');
                
                // Добавляем класс для дополнительного CSS
                input.classList.add('narrow-date-field');
            }
        });
        
        // Настраиваем ширину колонок таблицы
        const table = document.querySelector('#result_list');
        if (table) {
            // Находим заголовки и ячейки для колонок даты
            const headers = table.querySelectorAll('th');
            const rows = table.querySelectorAll('tbody tr');
            
            // Колонка "Планируемая дата" (обычно 9-я)
            if (headers[8]) { // nth-child(9) = index 8
                headers[8].style.setProperty('width', '150px', 'important');
                headers[8].style.setProperty('max-width', '150px', 'important');
                headers[8].style.setProperty('min-width', '150px', 'important');
            }
            
            // Колонка "Дата голосования" (обычно 10-я)
            if (headers[9]) { // nth-child(10) = index 9
                headers[9].style.setProperty('width', '150px', 'important');
                headers[9].style.setProperty('max-width', '150px', 'important');
                headers[9].style.setProperty('min-width', '150px', 'important');
            }
            
            // Настраиваем ячейки в строках
            rows.forEach(function(row) {
                const cells = row.querySelectorAll('td');
                if (cells[8]) { // Планируемая дата
                    cells[8].style.setProperty('width', '150px', 'important');
                    cells[8].style.setProperty('max-width', '150px', 'important');
                    cells[8].style.setProperty('min-width', '150px', 'important');
                }
                if (cells[9]) { // Дата голосования
                    cells[9].style.setProperty('width', '150px', 'important');
                    cells[9].style.setProperty('max-width', '150px', 'important');
                    cells[9].style.setProperty('min-width', '150px', 'important');
                }
            });
        }
    }
    
    // Применяем стили при загрузке страницы
    resizeDateFields();
    
    // Применяем стили с задержкой (на случай, если элементы загружаются асинхронно)
    setTimeout(resizeDateFields, 100);
    setTimeout(resizeDateFields, 500);
    setTimeout(resizeDateFields, 1000);
    
    // Применяем стили при изменении DOM (для динамически добавляемых элементов)
    const observer = new MutationObserver(function(mutations) {
        let shouldResize = false;
        mutations.forEach(function(mutation) {
            if (mutation.type === 'childList' && mutation.addedNodes.length > 0) {
                shouldResize = true;
            }
        });
        if (shouldResize) {
            setTimeout(resizeDateFields, 50);
        }
    });
    
    // Наблюдаем за изменениями в body
    observer.observe(document.body, {
        childList: true,
        subtree: true
    });
});