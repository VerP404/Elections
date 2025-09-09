// Автоматическое заполнение УИК при выборе агитатора
document.addEventListener('DOMContentLoaded', function() {
    const agitatorField = document.querySelector('#id_agitator');
    const uikField = document.querySelector('#id_uik');
    
    if (agitatorField && uikField) {
        // Функция для обновления УИК
        function updateUIK(agitatorId) {
            if (agitatorId) {
                // Получаем УИК агитатора через AJAX
                fetch(`/admin/elections/user/${agitatorId}/uik/`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.uik_id) {
                            uikField.value = data.uik_id;
                            // Обновляем отображение поля
                            if (uikField.tagName === 'SELECT') {
                                uikField.dispatchEvent(new Event('change'));
                            }
                        }
                    })
                    .catch(error => {
                        console.error('Ошибка при получении УИК агитатора:', error);
                    });
            } else {
                // Очищаем УИК если агитатор не выбран
                uikField.value = '';
                if (uikField.tagName === 'SELECT') {
                    uikField.dispatchEvent(new Event('change'));
                }
            }
        }
        
        // Обработчик для обычного select (если автодополнение отключено)
        agitatorField.addEventListener('change', function() {
            updateUIK(this.value);
        });
        
        // Обработчик для автодополнения (Unfold)
        // Слушаем изменения в скрытом поле (основной способ)
        agitatorField.addEventListener('change', function() {
            updateUIK(this.value);
        });
        
        // Дополнительные обработчики для автодополнения
        // Слушаем клики по результатам поиска
        document.addEventListener('click', function(e) {
            if (e.target.classList.contains('select2-results__option') || 
                e.target.closest('.select2-results__option')) {
                // Задержка для обновления скрытого поля
                setTimeout(() => {
                    updateUIK(agitatorField.value);
                }, 200);
            }
        });
        
        // Слушаем события select2 (если используется)
        $(document).on('select2:select', '#id_agitator', function(e) {
            setTimeout(() => {
                updateUIK(agitatorField.value);
            }, 100);
        });
        
        // Слушаем изменения через MutationObserver (для динамических изменений)
        const observer = new MutationObserver(function(mutations) {
            mutations.forEach(function(mutation) {
                if (mutation.type === 'attributes' && mutation.attributeName === 'value') {
                    if (mutation.target === agitatorField) {
                        updateUIK(agitatorField.value);
                    }
                }
            });
        });
        
        observer.observe(agitatorField, {
            attributes: true,
            attributeFilter: ['value']
        });
        
        // Инициализация при загрузке страницы
        if (agitatorField.value) {
            updateUIK(agitatorField.value);
        }
        
        // Дополнительный обработчик - слушаем все изменения в форме
        const form = agitatorField.closest('form');
        if (form) {
            form.addEventListener('change', function(e) {
                if (e.target === agitatorField) {
                    updateUIK(agitatorField.value);
                }
            });
        }
        
        // Периодическая проверка (fallback)
        let lastValue = agitatorField.value;
        setInterval(() => {
            if (agitatorField.value !== lastValue) {
                lastValue = agitatorField.value;
                updateUIK(agitatorField.value);
            }
        }, 500);
    }
});
