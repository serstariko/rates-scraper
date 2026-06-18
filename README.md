# Веб-интерфейс парсинга процентных ставок

Приложение собирает данные по процентным ставкам с нескольких сайтов и позволяет скачать все полученные результаты в формате Excel.

## Возможности

- Добавление/редактирование списка источников прямо в UI.
- Автоматическая загрузка данных при открытии страницы.
- Автообновление данных каждый час.
- Ручное обновление кнопкой **Обновить сейчас**.
- Быстрое добавление расширенного списка источников кнопкой **Добавить новые источники**.
- Поддержка нескольких стратегий парсинга:
  - `cbr_key_rate`
  - `ruonia_rate` (для https://cbr.ru/hd_base/ruonia/)
  - `ecb_key_rates`
  - `boe_bank_rate`
  - `ester_rate` (для https://www.global-rates.com/en/interest-rates/ester/)
  - `euribor_1m_rate` (для https://www.global-rates.com/en/interest-rates/euribor/)
  - `euribor_3m_rate` (для https://www.global-rates.com/en/interest-rates/euribor/)
  - `euribor_6m_rate` (для https://www.global-rates.com/en/interest-rates/euribor/)
  - `generic` (универсальный режим)
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
- `status` — `ok`, `no_rate_found`, `error`
- `details` — служебные детали парсинга
- `error` — текст ошибки (если есть)
- `collected_at_utc` — время сбора данных (UTC)
