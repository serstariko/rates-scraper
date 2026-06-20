# Веб-интерфейс парсинга процентных ставок

Приложение собирает данные по процентным ставкам с нескольких сайтов и позволяет скачать все полученные результаты в формате Excel.

## Возможности

- Фиксированный список источников по запросу: ключевая ставка ЦБ РФ, RUONIA, RUSFAR, RUSFAR3M, RUSFARCNY, SOFR, CME SOFR OIS (1Y/2Y/3Y/5Y/10Y), NFEASWAP (1W-1Y), ESTER, EURIBOR 1M/3M/6M.
- Автоматическая загрузка данных при открытии страницы.
- Автообновление данных каждый час.
- Ручное обновление кнопкой **Обновить сейчас**.
- Поддержка стратегий парсинга для выбранных источников:
  - `cbr_key_rate` (для https://cbr.ru/hd_base/KeyRate/)
  - `ruonia_rate` (для https://cbr.ru/hd_base/ruonia/)
  - `rusfar_rate` (MOEX ISS: индекс RUSFAR, поле `CURRENTVALUE`)
  - `rusfar3m_rate` (MOEX ISS: индекс RUSFAR3M, поле `CURRENTVALUE`)
  - `rusfarcny_rate` (MOEX ISS: индекс RUSFARCNY, поле `CURRENTVALUE`)
  - `sofr_rate` (NY Fed Markets API: SOFR, поле `dailyRate`)
  - `cme_sofr_swap_1y_rate` (CME Cleared SOFR Swaps, срок 1Y)
  - `cme_sofr_swap_2y_rate` (CME Cleared SOFR Swaps, срок 2Y)
  - `cme_sofr_swap_3y_rate` (CME Cleared SOFR Swaps, срок 3Y)
  - `cme_sofr_swap_5y_rate` (CME Cleared SOFR Swaps, срок 5Y)
  - `cme_sofr_swap_10y_rate` (CME Cleared SOFR Swaps, срок 10Y)
  - `nfeaswap_1w_rate` (NFEASWAP архив, срок 1W)
  - `nfeaswap_2w_rate` (NFEASWAP архив, срок 2W)
  - `nfeaswap_1m_rate` (NFEASWAP архив, срок 1M)
  - `nfeaswap_2m_rate` (NFEASWAP архив, срок 2M)
  - `nfeaswap_3m_rate` (NFEASWAP архив, срок 3M)
  - `nfeaswap_6m_rate` (NFEASWAP архив, срок 6M)
  - `nfeaswap_9m_rate` (NFEASWAP архив, срок 9M)
  - `nfeaswap_1y_rate` (NFEASWAP архив, срок 1Y)
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
