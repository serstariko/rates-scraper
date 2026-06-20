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


def main() -> None:
    st.set_page_config(page_title="Парсер процентных ставок", layout="wide")
    st.title("Парсер процентных ставок с выгрузкой в Excel")
    st.write(
        "Используется фиксированный список источников: RUONIA, RUSFAR, RUSFAR3M, RUSFARCNY, SOFR, "
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

    left, right = st.columns([1, 3])
    with left:
        refresh_now = st.button("Обновить сейчас", type="primary", use_container_width=True)
    with right:
        st.caption("Список источников зафиксирован по вашему запросу.")

    st.subheader("Используемые источники")
    st.dataframe(pd.DataFrame(DEFAULT_SOURCES), use_container_width=True, hide_index=True)

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
        st.dataframe(results, use_container_width=True)
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
