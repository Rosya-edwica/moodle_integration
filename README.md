# moodle_integration
Репозиторий создан для подтверждения гипотезы о связи курсов мудла с платформой Edwica


Подход работы с БД может показаться странным, но изначально я планировал выполнять запрос в виде транзакции, чтобы гарантировать правильную последовательность сохранения данных. Конечно, можно было поделить функции на более мелкие куски, где каждый кусок отвечает за работу в определенной таблице MySQL и все равно сохранить транзакцию. Но я выбрал такой путь.