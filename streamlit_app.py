from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO

import pandas as pd
import streamlit as st

from rate_scraper import SourceConfig, scrape_all_sources

try:
    from streamlit_autorefresh import st_autorefresh
except ImportError:  # pragma: no cover - fallback для окружений без пакета
    st_autorefresh = None

DEFAULT_SOURCES = [
    {
        "name": "Ключевая ставка — ЦБ РФ",
        "url": "https://cbr.ru/hd_base/KeyRate/",
        "parser": "cbr_key_rate",
    },
    {
        "name": "RUONIA — ЦБ РФ",
        "url": "https://cbr.ru/hd_base/ruonia/",
        "parser": "ruonia_rate",
    },
    {
        "name": "MOEX — RUSFAR (CURRENTVALUE)",
        "url": "https://iss.moex.com/iss/engines/stock/markets/index/securities/RUSFAR.json",
        "parser": "rusfar_rate",
    },
    {
        "name": "MOEX — RUSFAR3M (CURRENTVALUE)",
        "url": "https://iss.moex.com/iss/engines/stock/markets/index/securities/RUSFAR3M.json",
        "parser": "rusfar3m_rate",
    },
    {
        "name": "MOEX — RUSFARCNY (CURRENTVALUE)",
        "url": "https://iss.moex.com/iss/engines/stock/markets/index/securities/RUSFARCNY.json",
        "parser": "rusfarcny_rate",
    },
    {
        "name": "NY Fed — SOFR",
        "url": "https://www.newyorkfed.org/markets/reference-rates/sofr",
        "parser": "sofr_rate",
    },
    {
        "name": "CME SOFR OIS — 1Y",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_1y_rate",
    },
    {
        "name": "CME SOFR OIS — 2Y",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_2y_rate",
    },
    {
        "name": "CME SOFR OIS — 3Y",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_3y_rate",
    },
    {
        "name": "CME SOFR OIS — 4Y (расчет.)",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_4y_interp_rate",
    },
    {
        "name": "CME SOFR OIS — 5Y",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_5y_rate",
    },
    {
        "name": "CME SOFR OIS — 6Y (расчет.)",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_6y_interp_rate",
    },
    {
        "name": "CME SOFR OIS — 7Y (расчет.)",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_7y_interp_rate",
    },
    {
        "name": "CME SOFR OIS — 8Y (расчет.)",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_8y_interp_rate",
    },
    {
        "name": "CME SOFR OIS — 9Y (расчет.)",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_9y_interp_rate",
    },
    {
        "name": "CME SOFR OIS — 10Y",
        "url": "https://www.cmegroup.com/trading/interest-rates/cleared-otc-sofr-swaps.html",
        "parser": "cme_sofr_swap_10y_rate",
    },
    {
        "name": "NFEASWAP — 1W",
        "url": "https://nfeaswap.ru/",
        "parser": "nfeaswap_1w_rate",
    },
    {
        "name": "NFEASWAP — 2W",
        "url": "https://nfeaswap.ru/",
        "parser": "nfeaswap_2w_rate",
    },
    {
        "name": "NFEASWAP — 1M",
        "url": "https://nfeaswap.ru/",
        "parser": "nfeaswap_1m_rate",
    },
    {
        "name": "NFEASWAP — 2M",
        "url": "https://nfeaswap.ru/",
        "parser": "nfeaswap_2m_rate",
    },
    {
        "name": "NFEASWAP — 3M",
        "url": "https://nfeaswap.ru/",
        "parser": "nfeaswap_3m_rate",
    },
    {
        "name": "NFEASWAP — 6M",
        "url": "https://nfeaswap.ru/",
        "parser": "nfeaswap_6m_rate",
    },
    {
        "name": "NFEASWAP — 9M",
        "url": "https://nfeaswap.ru/",
        "parser": "nfeaswap_9m_rate",
    },
    {
        "name": "NFEASWAP — 1Y",
        "url": "https://nfeaswap.ru/",
        "parser": "nfeaswap_1y_rate",
    },
    {
        "name": "ESTER — global-rates",
        "url": "https://www.global-rates.com/en/interest-rates/ester/",
        "parser": "ester_rate",
    },
    {
        "name": "EURIBOR 1M — global-rates",
        "url": "https://www.global-rates.com/en/interest-rates/euribor/",
        "parser": "euribor_1m_rate",
    },
    {
        "name": "EURIBOR 3M — global-rates",
        "url": "https://www.global-rates.com/en/interest-rates/euribor/",
        "parser": "euribor_3m_rate",
    },
    {
        "name": "EURIBOR 6M — global-rates",
        "url": "https://www.global-rates.com/en/interest-rates/euribor/",
        "parser": "euribor_6m_rate",
    },
]

AUTO_REFRESH_MS = 60 * 60 * 1000


def _to_excel_bytes(dataframe: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="rates")
    output.seek(0)
    return output.read()


def _fixed_source_configs() -> list[SourceConfig]:
    return [SourceConfig(name=row["name"], url=row["url"], parser=row["parser"]) for row in DEFAULT_SOURCES]


def _refresh_results(source_configs: list[SourceConfig], reason: str) -> None:
    with st.spinner("Идёт сбор данных..."):
        st.session_state.results = scrape_all_sources(source_configs)
    st.session_state.last_refresh_at_utc = datetime.now(timezone.utc)
    st.session_state.last_refresh_reason = reason


def _build_summary_results_table(results: pd.DataFrame) -> pd.DataFrame:
    summary_columns = [
        "source_name",
        "rate_percent",
        "rate_date",
        "previous_rate_percent",
        "previous_rate_date",
        "absolute_change_percent",
        "relative_change_percent",
        "status",
        "collected_at_utc",
    ]
    existing_columns = [column for column in summary_columns if column in results.columns]
    summary = results[existing_columns].copy()
    summary = summary.rename(
        columns={
            "source_name": "Источник",
            "rate_percent": "Текущая ставка",
            "rate_date": "Дата текущей",
            "previous_rate_percent": "Предыдущая ставка",
            "previous_rate_date": "Дата предыдущей",
            "absolute_change_percent": "Изменение (абс.)",
            "relative_change_percent": "Изменение (%)",
            "status": "Статус",
            "collected_at_utc": "Собрано (UTC)",
        }
    )
    return summary


def _build_technical_results_table(results: pd.DataFrame) -> pd.DataFrame:
    technical_columns_order = [
        "source_name",
        "source_url",
        "parser",
        "rate_percent",
        "rate_date",
        "previous_rate_percent",
        "previous_rate_date",
        "relative_change_percent",
        "absolute_change_percent",
        "status",
        "details",
        "error",
        "collected_at_utc",
    ]
    columns = [column for column in technical_columns_order if column in results.columns]
    return results[columns].copy()


def main() -> None:
    st.set_page_config(page_title="Парсер процентных ставок", layout="wide")
    st.title("Парсер процентных ставок с выгрузкой в Excel")
    st.write(
        "Используется фиксированный список источников: ключевая ставка ЦБ РФ, RUONIA, "
        "RUSFAR, RUSFAR3M, RUSFARCNY, SOFR, CME SOFR OIS (1Y-10Y, с интерполяцией 4Y/6Y/7Y/8Y/9Y), "
        "NFEASWAP (1W-1Y), "
        "ESTER и EURIBOR 1M/3M/6M. "
        "Данные загружаются автоматически при открытии страницы, обновляются каждый час и по кнопке **Обновить сейчас**."
    )

    if "results" not in st.session_state:
        st.session_state.results = pd.DataFrame()
    if "last_refresh_at_utc" not in st.session_state:
        st.session_state.last_refresh_at_utc = None
    if "last_refresh_reason" not in st.session_state:
        st.session_state.last_refresh_reason = None
    if "last_auto_tick" not in st.session_state:
        st.session_state.last_auto_tick = 0

    auto_tick = 0
    if st_autorefresh is not None:
        auto_tick = st_autorefresh(interval=AUTO_REFRESH_MS, key="hourly_rates_refresh")
    else:
        st.warning(
            "Пакет streamlit-autorefresh не установлен: автообновление раз в час отключено. "
            "Работает только ручное обновление."
        )

    refresh_now = st.button("Обновить сейчас", type="primary", use_container_width=True)

    source_configs = _fixed_source_configs()

    refresh_reason: str | None = None
    if st.session_state.results.empty:
        refresh_reason = "initial"
    elif refresh_now:
        refresh_reason = "manual"
    elif st_autorefresh is not None and auto_tick != st.session_state.last_auto_tick:
        refresh_reason = "hourly"

    if refresh_reason:
        _refresh_results(source_configs, refresh_reason)
        st.success(f"Собрано источников: {len(st.session_state.results)}")

    st.session_state.last_auto_tick = auto_tick

    if st.session_state.last_refresh_at_utc is not None:
        reason_labels = {
            "initial": "первичная загрузка",
            "manual": "ручное обновление",
            "hourly": "автообновление (1 час)",
        }
        refreshed_at = st.session_state.last_refresh_at_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        refresh_label = reason_labels.get(st.session_state.last_refresh_reason, "обновление")
        st.caption(f"Последнее обновление: {refreshed_at} ({refresh_label}).")

    results = st.session_state.results
    if not results.empty:
        st.subheader("Результаты парсинга")
        status_counts = results["status"].value_counts(dropna=False).to_dict()
        ok_count = int(status_counts.get("ok", 0))
        error_count = int(status_counts.get("error", 0))
        not_found_count = int(status_counts.get("no_rate_found", 0))

        c1, c2, c3 = st.columns(3)
        c1.metric("OK", ok_count)
        c2.metric("Ошибка", error_count)
        c3.metric("Не найдено", not_found_count)

        status_options = ["Все", "ok", "no_rate_found", "error"]
        selected_status = st.selectbox(
            "Фильтр по статусу",
            options=status_options,
            index=0,
            key="results_status_filter",
        )

        filtered_results = results.copy()
        if selected_status != "Все":
            filtered_results = filtered_results[filtered_results["status"] == selected_status]

        summary_table = _build_summary_results_table(filtered_results)
        technical_table = _build_technical_results_table(filtered_results)

        summary_tab, technical_tab = st.tabs(["Основная таблица", "Технические детали"])
        with summary_tab:
            st.dataframe(
                summary_table,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Текущая ставка": st.column_config.NumberColumn(format="%.4f"),
                    "Предыдущая ставка": st.column_config.NumberColumn(format="%.4f"),
                    "Изменение (абс.)": st.column_config.NumberColumn(format="%.4f"),
                    "Изменение (%)": st.column_config.NumberColumn(format="%.4f"),
                },
            )
        with technical_tab:
            st.dataframe(technical_table, use_container_width=True, hide_index=True)

        st.download_button(
            label="Скачать Excel",
            data=_to_excel_bytes(results),
            file_name="interest_rates.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    else:
        st.info("Результаты появятся после запуска парсинга.")


if __name__ == "__main__":
    main()
