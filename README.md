# Веб-интерфейс парсинга процентных ставок

Приложение собирает данные по процентным ставкам с нескольких сайтов и позволяет скачать все полученные результаты в формате Excel.

## Возможности

- Фиксированный список источников по запросу: ключевая ставка ЦБ РФ, RUONIA, FR007, USD/CNY Swap Point (1W,1M,2M,3M,6M,9M,1Y-5Y), RUSFAR, RUSFAR3M, RUSFARCNY, OISFX, SOFR, CME SOFR OIS (1Y-10Y, расчётные 4Y/6Y/7Y/8Y/9Y по линейной интерполяции), NFEASWAP (1W-1Y), ESTER, EURIBOR 1M/3M/6M.
- Автоматическая загрузка данных при открытии страницы.
- Автообновление данных каждый час.
- Ручное обновление кнопкой **Обновить сейчас**.
- В блоке результатов: основная таблица, технические детали и фильтр по статусу (`ok`, `no_rate_found`, `error`).
- Поддержка стратегий парсинга для выбранных источников:
  - `cbr_key_rate` (для https://cbr.ru/hd_base/KeyRate/)
  - `ruonia_rate` (для https://cbr.ru/hd_base/ruonia/)
  - `fr007_rate` (для https://www.chinamoney.com.cn/english/bmkfrr/)
  - `usdcny_swap_point_1w_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 1W)
  - `usdcny_swap_point_1m_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 1M)
  - `usdcny_swap_point_2m_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 2M)
  - `usdcny_swap_point_3m_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 3M)
  - `usdcny_swap_point_6m_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 6M)
  - `usdcny_swap_point_9m_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 9M)
  - `usdcny_swap_point_1y_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 1Y)
  - `usdcny_swap_point_2y_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 2Y)
  - `usdcny_swap_point_3y_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 3Y)
  - `usdcny_swap_point_4y_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 4Y)
  - `usdcny_swap_point_5y_rate` (ChinaMoney USD/CNY FX Swap Curve, Swap Point (Pips), срок 5Y)
  - `rusfar_rate` (MOEX ISS: индекс RUSFAR, поле `CURRENTVALUE`)
  - `rusfar3m_rate` (MOEX ISS: индекс RUSFAR3M, поле `CURRENTVALUE`)
  - `rusfarcny_rate` (MOEX ISS: индекс RUSFARCNY, поле `CURRENTVALUE`)
  - `oisfx_rate` (MOEX ISS: индекс OISFIXUSD, поле `CURRENTVALUE`)
  - `sofr_rate` (NY Fed Markets API: SOFR, поле `dailyRate`)
  - `cme_sofr_swap_1y_rate` (CME Cleared SOFR Swaps, срок 1Y)
  - `cme_sofr_swap_2y_rate` (CME Cleared SOFR Swaps, срок 2Y)
  - `cme_sofr_swap_3y_rate` (CME Cleared SOFR Swaps, срок 3Y)
  - `cme_sofr_swap_4y_interp_rate` (CME Cleared SOFR Swaps, расчётный срок 4Y)
  - `cme_sofr_swap_5y_rate` (CME Cleared SOFR Swaps, срок 5Y)
  - `cme_sofr_swap_6y_interp_rate` (CME Cleared SOFR Swaps, расчётный срок 6Y)
  - `cme_sofr_swap_7y_interp_rate` (CME Cleared SOFR Swaps, расчётный срок 7Y)
  - `cme_sofr_swap_8y_interp_rate` (CME Cleared SOFR Swaps, расчётный срок 8Y)
  - `cme_sofr_swap_9y_interp_rate` (CME Cleared SOFR Swaps, расчётный срок 9Y)
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
