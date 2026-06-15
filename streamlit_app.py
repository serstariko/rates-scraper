from __future__ import annotations

from io import BytesIO

import pandas as pd
import streamlit as st

from rate_scraper import SourceConfig, scrape_all_sources

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


def main() -> None:
    st.set_page_config(page_title="Парсер процентных ставок", layout="wide")
    st.title("Парсер процентных ставок с выгрузкой в Excel")
    st.write(
        "Добавьте сайты-источники ставок, нажмите **Собрать данные**, "
        "после чего можно скачать итоговую таблицу в формате Excel."
    )

    if "sources" not in st.session_state:
        st.session_state.sources = pd.DataFrame(DEFAULT_SOURCES)
    if "results" not in st.session_state:
        st.session_state.results = pd.DataFrame()

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

    left, right = st.columns([1, 3])
    with left:
        collect = st.button("Собрать данные", type="primary", use_container_width=True)
    with right:
        st.caption("Для неизвестных сайтов используйте parser = generic.")

    if collect:
        if not source_configs:
            st.warning("Добавьте хотя бы один валидный источник.")
        else:
            with st.spinner("Идёт сбор данных..."):
                st.session_state.results = scrape_all_sources(source_configs)
            st.success(f"Собрано источников: {len(st.session_state.results)}")

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
