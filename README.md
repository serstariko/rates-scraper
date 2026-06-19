# Веб-интерфейс парсинга процентных ставок

Приложение собирает данные по процентным ставкам с нескольких сайтов и позволяет скачать все полученные результаты в формате Excel.

## Возможности

- Фиксированный список источников по запросу: RUONIA, ESTER, EURIBOR 1M/3M/6M.
- Автоматическая загрузка данных при открытии страницы.
- Автообновление данных каждый час.
- Ручное обновление кнопкой **Обновить сейчас**.
- Поддержка стратегий парсинга для выбранных источников:
  - `ruonia_rate` (для https://cbr.ru/hd_base/ruonia/)
  - `ester_rate` (для https://www.global-rates.com/en/interest-rates/ester/)
  - `euribor_1m_rate` (для https://www.global-rates.com/en/interest-rates/euribor/)
  - `euribor_3m_rate` (для https://www.global-rates.com/en/interest-rates/euribor/)
  - `euribor_6m_rate` (для https://www.global-rates.com/en/interest-rates/euribor/)
- Выгрузка итоговой таблицы в файл `interest_rates.xlsx`.

## Запуск

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run streamlit_app.py
```

После запуска откройте URL, который покажет Streamlit (обычно `http://localhost:8501`).

Данные подтягиваются автоматически при открытии страницы и далее обновляются каждый час, пока вкладка открыта.

## Формат результата

В таблицу попадают:

- `source_name` — название источника
- `source_url` — URL источника
- `parser` — тип парсера
- `rate_percent` — найденная ставка в процентах
- `rate_date` — дата ставки (если извлечена)
- `previous_rate_percent` — предыдущее значение ставки
- `previous_rate_date` — дата предыдущего значения
- `relative_change_percent` — относительное изменение, % (`(текущее - предыдущее) / предыдущее * 100`)
- `absolute_change_percent` — абсолютное изменение (`текущее - предыдущее`)
- `status` — `ok`, `no_rate_found`, `error`
- `details` — служебные детали парсинга
- `error` — текст ошибки (если есть)
- `collected_at_utc` — время сбора данных (UTC)
