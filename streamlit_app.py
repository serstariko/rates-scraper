from __future__ import annotations

from datetime import datetime, timezone
from io import BytesIO
import json
from pathlib import Path

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

RECOMMENDED_EXTRA_SOURCES = [
    {
        "name": "RUONIA — ЦБ РФ",
        "url": "https://cbr.ru/hd_base/ruonia/",
        "parser": "ruonia_rate",
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
    {
        "name": "ФРС США — Interest on Reserve Balances",
        "url": "https://www.federalreserve.gov/monetarypolicy/openmarket.htm",
        "parser": "generic",
    },
    {
        "name": "Швейцарский НБ — SNB policy rate",
        "url": "https://www.snb.ch/en/iabout/monpol/id/monpol",
        "parser": "generic",
    },
    {
        "name": "Банк Канады — Policy interest rate",
        "url": "https://www.bankofcanada.ca/core-functions/monetary-policy/key-interest-rate/",
        "parser": "generic",
    },
    {
        "name": "РБА (Австралия) — Cash Rate Target",
        "url": "https://www.rba.gov.au/statistics/cash-rate/",
        "parser": "generic",
    },
    {
        "name": "Резервный банк Новой Зеландии — Official Cash Rate",
        "url": "https://www.rbnz.govt.nz/monetary-policy/official-cash-rate-decisions",
        "parser": "generic",
    },
    {
        "name": "Норвежский банк — Policy rate",
        "url": "https://www.norges-bank.no/en/topics/Monetary-policy/Policy-rate/",
        "parser": "generic",
    },
    {
        "name": "Риксбанк (Швеция) — Policy rate",
        "url": "https://www.riksbank.se/en-gb/statistics/search-interest--exchange-rates/repo-rate-historical-data/",
        "parser": "generic",
    },
    {
        "name": "Банк Японии — Basic Discount Rate",
        "url": "https://www.boj.or.jp/en/statistics/boj/other/discount/index.htm/",
        "parser": "generic",
    },
]

AUTO_REFRESH_MIN_OPTIONS = [5, 15, 30, 60, 120]
DEFAULT_AUTO_REFRESH_MINUTES = 60
CALENDAR_COLUMNS = [
    "Beijing",
    "Europe",
    "NewYork",
    "RUONIA",
    "RUSFAR",
    "RUSFARCNY",
    "MOSCOW",
    "SPFI",
]
HOLIDAY_CALENDARS_PATH = Path(__file__).resolve().parent / ".holiday_calendars.json"


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


def _append_missing_sources(
    current_sources: pd.DataFrame, candidate_sources: list[dict[str, str]]
) -> tuple[pd.DataFrame, int]:
    if current_sources.empty:
        current_sources = pd.DataFrame(columns=["name", "url", "parser"])

    existing_keys = set()
    for row in current_sources.to_dict("records"):
        url = str(row.get("url", "")).strip().lower()
        parser = str(row.get("parser", "generic")).strip().lower()
        if url:
            existing_keys.add((url, parser))

    additions = []
    for source in candidate_sources:
        source_key = (source["url"].strip().lower(), source["parser"].strip().lower())
        if source_key in existing_keys:
            continue
        additions.append(source)
        existing_keys.add(source_key)

    if not additions:
        return current_sources, 0

    updated = pd.concat([current_sources, pd.DataFrame(additions)], ignore_index=True)
    return updated, len(additions)


def _sources_signature(sources: list[SourceConfig]) -> tuple[tuple[str, str, str], ...]:
    return tuple((source.name, source.url, source.parser) for source in sources)


def _refresh_results(source_configs: list[SourceConfig], reason: str) -> None:
    with st.spinner("Идёт сбор данных..."):
        st.session_state.results = scrape_all_sources(source_configs)
    st.session_state.last_refresh_at_utc = datetime.now(timezone.utc)
    st.session_state.last_refresh_reason = reason


def _format_calendar_date(value: str) -> str | None:
    cleaned = value.strip()
    if not cleaned:
        return None

    known_formats = (
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%Y/%m/%d",
    )
    for date_format in known_formats:
        try:
            parsed = datetime.strptime(cleaned, date_format)
            return parsed.strftime("%d.%m.%Y")
        except ValueError:
            continue
    return None


def _calendar_dict_to_dataframe(calendars: dict[str, list[str]]) -> pd.DataFrame:
    normalized: dict[str, list[str]] = {}
    max_len = 0
    for column in CALENDAR_COLUMNS:
        values = calendars.get(column, [])
        unique_values = sorted(
            {value for value in values if value},
            key=lambda value: datetime.strptime(value, "%d.%m.%Y"),
        )
        normalized[column] = unique_values
        max_len = max(max_len, len(unique_values))

    if max_len == 0:
        max_len = 1

    table_data: dict[str, list[str]] = {}
    for column in CALENDAR_COLUMNS:
        column_values = normalized[column]
        table_data[column] = column_values + [""] * (max_len - len(column_values))
    return pd.DataFrame(table_data)


def _calendar_dataframe_to_dict(
    dataframe: pd.DataFrame,
) -> tuple[dict[str, list[str]], list[str]]:
    calendars: dict[str, list[str]] = {column: [] for column in CALENDAR_COLUMNS}
    invalid_values: list[str] = []

    for column in CALENDAR_COLUMNS:
        if column not in dataframe.columns:
            continue
        values_for_column: set[str] = set()
        for raw_value in dataframe[column].tolist():
            if pd.isna(raw_value):
                continue
            text_value = str(raw_value).strip()
            if not text_value:
                continue
            formatted_value = _format_calendar_date(text_value)
            if formatted_value is None:
                invalid_values.append(f"{column}: {text_value}")
                continue
            values_for_column.add(formatted_value)
        calendars[column] = sorted(
            values_for_column, key=lambda value: datetime.strptime(value, "%d.%m.%Y")
        )

    return calendars, invalid_values


def _load_holiday_calendars() -> dict[str, list[str]]:
    try:
        raw_text = HOLIDAY_CALENDARS_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {column: [] for column in CALENDAR_COLUMNS}
    except OSError:
        return {column: [] for column in CALENDAR_COLUMNS}

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return {column: [] for column in CALENDAR_COLUMNS}

    if not isinstance(payload, dict):
        return {column: [] for column in CALENDAR_COLUMNS}

    cleaned_payload: dict[str, list[str]] = {column: [] for column in CALENDAR_COLUMNS}
    for column in CALENDAR_COLUMNS:
        values = payload.get(column, [])
        if not isinstance(values, list):
            continue
        formatted_values: set[str] = set()
        for value in values:
            if not isinstance(value, str):
                continue
            formatted = _format_calendar_date(value)
            if formatted:
                formatted_values.add(formatted)
        cleaned_payload[column] = sorted(
            formatted_values, key=lambda date_value: datetime.strptime(date_value, "%d.%m.%Y")
        )
    return cleaned_payload


def _save_holiday_calendars(calendars: dict[str, list[str]]) -> None:
    normalized_payload = {column: calendars.get(column, []) for column in CALENDAR_COLUMNS}
    HOLIDAY_CALENDARS_PATH.write_text(
        json.dumps(normalized_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main() -> None:
    st.set_page_config(page_title="Парсер процентных ставок", layout="wide")
    st.title("Парсер процентных ставок с выгрузкой в Excel")
    st.write(
        "Добавьте сайты-источники ставок: данные загружаются автоматически при открытии страницы, "
        "обновляются каждый час и по кнопке **Обновить сейчас**. "
        "Во вкладке **Календари** можно редактировать списки праздничных дат."
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
    if "auto_refresh_enabled" not in st.session_state:
        st.session_state.auto_refresh_enabled = True
    if "auto_refresh_minutes" not in st.session_state:
        st.session_state.auto_refresh_minutes = DEFAULT_AUTO_REFRESH_MINUTES
    if "holiday_calendars" not in st.session_state:
        st.session_state.holiday_calendars = _calendar_dict_to_dataframe(_load_holiday_calendars())

    parsing_tab, calendars_tab = st.tabs(["Парсинг ставок", "Календари"])

    with parsing_tab:
        auto_tick = 0
        if st.session_state.auto_refresh_enabled and st_autorefresh is not None:
            auto_tick = st_autorefresh(
                interval=st.session_state.auto_refresh_minutes * 60 * 1000,
                key="rates_auto_refresh",
            )
        elif st.session_state.auto_refresh_enabled and st_autorefresh is None:
            st.warning(
                "Пакет streamlit-autorefresh не установлен: автообновление раз в час отключено. "
                "Работает только ручное обновление."
            )

        left, middle, right = st.columns([1, 1.3, 2.2])
        with left:
            refresh_now = st.button("Обновить сейчас", type="primary", use_container_width=True)
        with middle:
            add_sources = st.button("Добавить новые источники", use_container_width=True)
        with right:
            st.caption("Для неизвестных сайтов используйте parser = generic.")

        with st.expander("Настройки автообновления", expanded=False):
            st.checkbox("Включить автообновление", key="auto_refresh_enabled")
            st.selectbox(
                "Интервал обновления (минуты)",
                options=AUTO_REFRESH_MIN_OPTIONS,
                key="auto_refresh_minutes",
            )

        if add_sources:
            updated_sources, added_count = _append_missing_sources(
                st.session_state.sources, RECOMMENDED_EXTRA_SOURCES
            )
            st.session_state.sources = updated_sources
            if added_count:
                st.success(f"Добавлено источников: {added_count}")
            else:
                st.info("Все рекомендованные источники уже есть в таблице.")
            st.rerun()

        source_editor = st.data_editor(
            st.session_state.sources,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "name": st.column_config.TextColumn("Название источника", required=True),
                "url": st.column_config.TextColumn("URL", required=True),
                "parser": st.column_config.SelectboxColumn(
                    "Парсер",
                    options=[
                        "cbr_key_rate",
                        "ruonia_rate",
                        "ecb_key_rates",
                        "boe_bank_rate",
                        "ester_rate",
                        "euribor_1m_rate",
                        "euribor_3m_rate",
                        "euribor_6m_rate",
                        "generic",
                    ],
                    required=True,
                ),
            },
            key="sources_editor",
        )

        st.session_state.sources = source_editor
        source_configs = _prepare_sources(source_editor)
        current_signature = _sources_signature(source_configs)
        previous_signature = st.session_state.sources_signature

        refresh_reason: str | None = None
        if st.session_state.results.empty:
            refresh_reason = "initial"
        elif refresh_now:
            refresh_reason = "manual"
        elif (
            st.session_state.auto_refresh_enabled
            and st_autorefresh is not None
            and auto_tick != st.session_state.last_auto_tick
        ):
            refresh_reason = "auto"
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
                "auto": f"автообновление ({st.session_state.auto_refresh_minutes} мин.)",
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

    with calendars_tab:
        st.subheader("Календари праздничных дней")
        st.caption(
            "Суббота и воскресенье считаются выходными автоматически. "
            "В таблице ниже указываются только дополнительные праздничные даты."
        )
        calendars_editor = st.data_editor(
            st.session_state.holiday_calendars,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            key="holiday_calendars_editor",
            column_config={
                column: st.column_config.TextColumn(
                    column,
                    help="Формат даты: ДД.ММ.ГГГГ (также поддерживаются YYYY-MM-DD, DD/MM/YYYY).",
                )
                for column in CALENDAR_COLUMNS
            },
        )
        st.session_state.holiday_calendars = calendars_editor

        save_column, reload_column, hint_column = st.columns([1, 1, 2.5])
        with save_column:
            save_calendars = st.button(
                "Сохранить календари",
                type="primary",
                use_container_width=True,
                key="save_holiday_calendars_button",
            )
        with reload_column:
            reload_calendars = st.button(
                "Перезагрузить из файла",
                use_container_width=True,
                key="reload_holiday_calendars_button",
            )
        with hint_column:
            st.caption("Добавляйте/удаляйте строки в таблице напрямую и затем нажимайте «Сохранить календари».")

        if save_calendars:
            normalized_calendars, invalid_values = _calendar_dataframe_to_dict(calendars_editor)
            if invalid_values:
                invalid_preview = ", ".join(invalid_values[:8])
                if len(invalid_values) > 8:
                    invalid_preview += ", ..."
                st.error(
                    "Найдены даты в некорректном формате. "
                    f"Проверьте значения: {invalid_preview}"
                )
            else:
                try:
                    _save_holiday_calendars(normalized_calendars)
                except OSError as exc:
                    st.error(f"Не удалось сохранить календари: {exc}")
                else:
                    st.session_state.holiday_calendars = _calendar_dict_to_dataframe(
                        normalized_calendars
                    )
                    st.success("Календари сохранены.")
                    st.rerun()

        if reload_calendars:
            st.session_state.holiday_calendars = _calendar_dict_to_dataframe(
                _load_holiday_calendars()
            )
            st.success("Календари загружены из файла.")
            st.rerun()


if __name__ == "__main__":
    main()
