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
        "name": "ЦБ РФ — ключевая ставка",
        "url": "https://www.cbr.ru/hd_base/keyrate/",
        "parser": "cbr_key_rate",
    },
    {
        "name": "ЕЦБ — ключевые ставки",
        "url": "https://www.ecb.europa.eu/stats/policy_and_exchange_rates/key_ecb_interest_rates/html/index.en.html",
        "parser": "ecb_key_rates",
    },
    {
        "name": "Банк Англии — Bank Rate",
        "url": "https://www.bankofengland.co.uk/boeapps/database/Bank-Rate.asp",
        "parser": "boe_bank_rate",
    },
]

AUTO_REFRESH_MS = 60 * 60 * 1000


def _to_excel_bytes(dataframe: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="rates")
    output.seek(0)
    return output.read()


def _prepare_sources(raw_sources: pd.DataFrame) -> list[SourceConfig]:
    cleaned = []
    for row in raw_sources.to_dict("records"):
        name = str(row.get("name", "")).strip()
        url = str(row.get("url", "")).strip()
        parser = str(row.get("parser", "generic")).strip()
        if not name or not url:
            continue
        cleaned.append(SourceConfig(name=name, url=url, parser=parser))
    return cleaned


def _sources_signature(sources: list[SourceConfig]) -> tuple[tuple[str, str, str], ...]:
    return tuple((source.name, source.url, source.parser) for source in sources)


def _refresh_results(source_configs: list[SourceConfig], reason: str) -> None:
    with st.spinner("Идёт сбор данных..."):
        st.session_state.results = scrape_all_sources(source_configs)
    st.session_state.last_refresh_at_utc = datetime.now(timezone.utc)
    st.session_state.last_refresh_reason = reason


def main() -> None:
    st.set_page_config(page_title="Парсер процентных ставок", layout="wide")
    st.title("Парсер процентных ставок с выгрузкой в Excel")
    st.write(
        "Добавьте сайты-источники ставок: данные загружаются автоматически при открытии страницы, "
        "обновляются каждый час и по кнопке **Обновить сейчас**."
    )

    if "sources" not in st.session_state:
        st.session_state.sources = pd.DataFrame(DEFAULT_SOURCES)
    if "results" not in st.session_state:
        st.session_state.results = pd.DataFrame()
    if "last_refresh_at_utc" not in st.session_state:
        st.session_state.last_refresh_at_utc = None
    if "last_refresh_reason" not in st.session_state:
        st.session_state.last_refresh_reason = None
    if "sources_signature" not in st.session_state:
        st.session_state.sources_signature = None
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

    source_editor = st.data_editor(
        st.session_state.sources,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "name": st.column_config.TextColumn("Название источника", required=True),
            "url": st.column_config.TextColumn("URL", required=True),
            "parser": st.column_config.SelectboxColumn(
                "Парсер",
                options=["cbr_key_rate", "ecb_key_rates", "boe_bank_rate", "generic"],
                required=True,
            ),
        },
        key="sources_editor",
    )

    st.session_state.sources = source_editor
    source_configs = _prepare_sources(source_editor)
    current_signature = _sources_signature(source_configs)
    previous_signature = st.session_state.sources_signature

    left, right = st.columns([1, 3])
    with left:
        refresh_now = st.button("Обновить сейчас", type="primary", use_container_width=True)
    with right:
        st.caption("Для неизвестных сайтов используйте parser = generic.")

    refresh_reason: str | None = None
    if st.session_state.results.empty:
        refresh_reason = "initial"
    elif refresh_now:
        refresh_reason = "manual"
    elif st_autorefresh is not None and auto_tick != st.session_state.last_auto_tick:
        refresh_reason = "hourly"
    elif previous_signature is not None and current_signature != previous_signature:
        refresh_reason = "sources_changed"

    if refresh_reason:
        if not source_configs:
            st.session_state.results = pd.DataFrame()
            st.warning("Добавьте хотя бы один валидный источник.")
        else:
            _refresh_results(source_configs, refresh_reason)
            st.success(f"Собрано источников: {len(st.session_state.results)}")

    st.session_state.sources_signature = current_signature
    st.session_state.last_auto_tick = auto_tick

    if st.session_state.last_refresh_at_utc is not None:
        reason_labels = {
            "initial": "первичная загрузка",
            "manual": "ручное обновление",
            "hourly": "автообновление (1 час)",
            "sources_changed": "изменение списка источников",
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
