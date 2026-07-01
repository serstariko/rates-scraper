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
        "name": "ChinaMoney — FR007",
        "url": "https://www.chinamoney.com.cn/english/bmkfrr/",
        "parser": "fr007_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 1W",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_1w_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 1M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_1m_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 2M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_2m_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 3M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_3m_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 6M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_6m_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 9M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_9m_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 1Y",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_1y_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 2Y",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_2y_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 3Y",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_3y_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 4Y",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_4y_rate",
    },
    {
        "name": "ChinaMoney USD/CNY Swap Point — 5Y",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "usdcny_swap_point_5y_rate",
    },
    {
        "name": "ChinaMoney EUR/USD Swap Point — 1W",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "eurusd_swap_point_1w_rate",
    },
    {
        "name": "ChinaMoney EUR/USD Swap Point — 2W",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "eurusd_swap_point_2w_rate",
    },
    {
        "name": "ChinaMoney EUR/USD Swap Point — 1M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "eurusd_swap_point_1m_rate",
    },
    {
        "name": "ChinaMoney EUR/USD Swap Point — 2M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "eurusd_swap_point_2m_rate",
    },
    {
        "name": "ChinaMoney EUR/USD Swap Point — 3M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "eurusd_swap_point_3m_rate",
    },
    {
        "name": "ChinaMoney EUR/USD Swap Point — 6M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "eurusd_swap_point_6m_rate",
    },
    {
        "name": "ChinaMoney EUR/USD Swap Point — 9M",
        "url": "https://www.chinamoney.com.cn/english/bmkycvfsc/",
        "parser": "eurusd_swap_point_9m_rate",
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
        "name": "MOEX — OISFX (OISFIXUSD)",
        "url": "https://www.moex.com/ru/index/OISFIXUSD",
        "parser": "oisfx_rate",
    },
    {
        "name": "NY Fed — SOFR",
        "url": "https://www.newyorkfed.org/markets/reference-rates/sofr",
        "parser": "sofr_rate",
    },
    {
        "name": "Cbonds — SOFR 1M (Index 72053)",
        "url": "https://cbonds.ru/indexes/72053/",
        "parser": "cbonds_index_rate",
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
RATE_CALENDAR_MAPPING_PATH = Path(__file__).resolve().parent / ".rate_calendar_mapping.json"
RATE_MAPPING_COLUMNS = ["source_name", "Calendar", "Shift"]


def _to_excel_bytes(dataframe: pd.DataFrame) -> bytes:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        dataframe.to_excel(writer, index=False, sheet_name="rates")
    output.seek(0)
    return output.read()


def _fixed_source_configs() -> list[SourceConfig]:
    return [SourceConfig(name=row["name"], url=row["url"], parser=row["parser"]) for row in DEFAULT_SOURCES]


def _refresh_results(
    source_configs: list[SourceConfig],
    reason: str,
    cbonds_credentials: tuple[str, str] | None = None,
) -> None:
    with st.spinner("Идёт сбор данных..."):
        st.session_state.results = scrape_all_sources(
            source_configs, cbonds_credentials=cbonds_credentials
        )
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


def _default_rate_calendar_mapping(source_name: str) -> tuple[str, int]:
    if source_name == "Ключевая ставка — ЦБ РФ":
        return "MOSCOW", 0
    if source_name == "RUONIA — ЦБ РФ":
        return "RUONIA", -1
    if source_name == "ChinaMoney — FR007":
        return "Beijing", 0
    if source_name.startswith("ChinaMoney USD/CNY Swap Point"):
        return "SPFI", 0
    if source_name.startswith("ChinaMoney EUR/USD Swap Point"):
        return "SPFI", 0
    if source_name.startswith("MOEX — RUSFAR"):
        return "RUSFAR", 0
    if source_name == "MOEX — OISFX (OISFIXUSD)":
        return "MOSCOW/NewYork", -1
    if source_name == "NY Fed — SOFR":
        return "NewYork", -1
    if source_name == "Cbonds — SOFR 1M (Index 72053)":
        return "SPFI", 0
    if source_name.startswith("CME SOFR OIS"):
        return "SPFI", 0
    if source_name.startswith("NFEASWAP"):
        return "SPFI", 0
    if source_name.startswith("ESTER"):
        return "Europe", -1
    if source_name.startswith("EURIBOR"):
        return "Europe", -1
    return "SPFI", 0


def _to_int_shift(value: object, default: int | None = None) -> int | None:
    if value is None:
        return default
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    text_value = str(value).strip()
    if not text_value:
        return default
    try:
        return int(float(text_value))
    except ValueError:
        return default


def _empty_rate_calendar_mapping_df() -> pd.DataFrame:
    return pd.DataFrame(columns=RATE_MAPPING_COLUMNS)


def _load_rate_calendar_mapping() -> pd.DataFrame:
    try:
        raw_text = RATE_CALENDAR_MAPPING_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return _empty_rate_calendar_mapping_df()
    except OSError:
        return _empty_rate_calendar_mapping_df()

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError:
        return _empty_rate_calendar_mapping_df()

    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, dict):
        rows = []
        for source_name, values in payload.items():
            if not isinstance(values, dict):
                continue
            rows.append(
                {
                    "source_name": source_name,
                    "Calendar": values.get("Calendar"),
                    "Shift": values.get("Shift"),
                }
            )
        return pd.DataFrame(rows)
    return _empty_rate_calendar_mapping_df()


def _sync_rate_calendar_mapping(
    mapping_df: pd.DataFrame, source_names: list[str]
) -> pd.DataFrame:
    existing: dict[str, dict[str, object]] = {}
    if not mapping_df.empty:
        for row in mapping_df.to_dict("records"):
            source_name = str(row.get("source_name", "")).strip()
            if not source_name or source_name in existing:
                continue
            existing[source_name] = {
                "Calendar": str(row.get("Calendar", "")).strip(),
                "Shift": _to_int_shift(row.get("Shift"), default=None),
            }

    rows: list[dict[str, object]] = []
    for source_name in source_names:
        default_calendar, default_shift = _default_rate_calendar_mapping(source_name)
        existing_row = existing.get(source_name, {})
        calendar_value = str(existing_row.get("Calendar", "")).strip() or default_calendar
        shift_value = _to_int_shift(existing_row.get("Shift"), default=default_shift)
        if shift_value is None:
            shift_value = default_shift
        rows.append(
            {
                "source_name": source_name,
                "Calendar": calendar_value,
                "Shift": shift_value,
            }
        )
    return pd.DataFrame(rows, columns=RATE_MAPPING_COLUMNS)


def _save_rate_calendar_mapping(mapping_df: pd.DataFrame) -> None:
    payload = mapping_df[RATE_MAPPING_COLUMNS].to_dict("records")
    RATE_CALENDAR_MAPPING_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _validate_rate_calendar_mapping(
    mapping_df: pd.DataFrame, source_names: list[str]
) -> tuple[pd.DataFrame, list[str]]:
    synced = _sync_rate_calendar_mapping(mapping_df, source_names)
    errors: list[str] = []

    for row in synced.to_dict("records"):
        source_name = str(row["source_name"])
        calendar_value = str(row.get("Calendar", "")).strip()
        shift_value = _to_int_shift(row.get("Shift"), default=None)

        if not calendar_value:
            errors.append(f"{source_name}: пустой календарь")
        if shift_value is None:
            errors.append(f"{source_name}: некорректный Shift")
        else:
            row["Shift"] = shift_value

    if errors:
        return synced, errors
    return synced, []


def _calendar_options_for_mapping(mapping_df: pd.DataFrame) -> list[str]:
    options = set(CALENDAR_COLUMNS)
    if "Calendar" in mapping_df.columns:
        options.update(
            {
                str(value).strip()
                for value in mapping_df["Calendar"].tolist()
                if str(value).strip()
            }
        )
    return sorted(options)


def main() -> None:
    st.set_page_config(page_title="Парсер процентных ставок", layout="wide")
    st.title("Парсер процентных ставок с выгрузкой в Excel")
    st.write(
        "Используется фиксированный список источников: ключевая ставка ЦБ РФ, RUONIA, FR007, "
        "USD/CNY Swap Point (1W,1M,2M,3M,6M,9M,1Y-5Y), "
        "EUR/USD Swap Point (1W,2W,1M,2M,3M,6M,9M), "
        "RUSFAR, RUSFAR3M, RUSFARCNY, OISFX, SOFR, Cbonds SOFR 1M, "
        "CME SOFR OIS (1Y-10Y, с интерполяцией 4Y/6Y/7Y/8Y/9Y), "
        "NFEASWAP (1W-1Y), "
        "ESTER и EURIBOR 1M/3M/6M. "
        "Данные загружаются автоматически при открытии страницы, обновляются каждый час и по кнопке **Обновить сейчас**. "
        "Во вкладках **Календари** и **Маппинг ставок** можно настраивать праздничные даты и соответствие ставок календарям/сдвигам."
    )
    with st.expander("Авторизация Cbonds (для закрытых источников)", expanded=False):
        cbonds_login = st.text_input(
            "Логин Cbonds",
            key="cbonds_login",
            autocomplete="username",
            help="Нужен для источников с parser=cbonds_index_rate.",
        )
        cbonds_password = st.text_input(
            "Пароль Cbonds",
            type="password",
            key="cbonds_password",
            autocomplete="current-password",
        )
        st.caption(
            "Учётные данные используются только для текущего запуска обновления и не выгружаются в результаты."
        )

    if "results" not in st.session_state:
        st.session_state.results = pd.DataFrame()
    if "last_refresh_at_utc" not in st.session_state:
        st.session_state.last_refresh_at_utc = None
    if "last_refresh_reason" not in st.session_state:
        st.session_state.last_refresh_reason = None
    if "last_auto_tick" not in st.session_state:
        st.session_state.last_auto_tick = 0
    if "holiday_calendars" not in st.session_state:
        st.session_state.holiday_calendars = _calendar_dict_to_dataframe(_load_holiday_calendars())

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
    source_names_for_mapping = [source.name for source in source_configs]

    if "rate_calendar_mapping" not in st.session_state:
        st.session_state.rate_calendar_mapping = _sync_rate_calendar_mapping(
            _load_rate_calendar_mapping(), source_names_for_mapping
        )
    else:
        st.session_state.rate_calendar_mapping = _sync_rate_calendar_mapping(
            st.session_state.rate_calendar_mapping, source_names_for_mapping
        )

    refresh_reason: str | None = None
    if st.session_state.results.empty:
        refresh_reason = "initial"
    elif refresh_now:
        refresh_reason = "manual"
    elif st_autorefresh is not None and auto_tick != st.session_state.last_auto_tick:
        refresh_reason = "hourly"

    cbonds_login = str(cbonds_login).strip()
    cbonds_password = str(cbonds_password).strip()
    cbonds_credentials: tuple[str, str] | None = None
    if cbonds_login and cbonds_password:
        cbonds_credentials = (cbonds_login, cbonds_password)
    elif cbonds_login or cbonds_password:
        st.warning("Для Cbonds укажите и логин, и пароль (или оставьте оба поля пустыми).")

    if (
        refresh_reason is None
        and cbonds_credentials is not None
        and not st.session_state.results.empty
        and "parser" in st.session_state.results.columns
    ):
        cbonds_rows = st.session_state.results[
            st.session_state.results["parser"] == "cbonds_index_rate"
        ]
        if not cbonds_rows.empty and "details" in cbonds_rows.columns:
            cbonds_details_text = " ".join(
                cbonds_rows["details"].fillna("").astype(str).tolist()
            ).lower()
            if (
                "логин/пароль не указаны" in cbonds_details_text
                or "логин и пароль не должны быть пустыми" in cbonds_details_text
            ):
                refresh_reason = "cbonds_credentials_updated"

    if refresh_reason:
        _refresh_results(source_configs, refresh_reason, cbonds_credentials=cbonds_credentials)
        st.success(f"Собрано источников: {len(st.session_state.results)}")

    st.session_state.last_auto_tick = auto_tick

    if st.session_state.last_refresh_at_utc is not None:
        reason_labels = {
            "initial": "первичная загрузка",
            "manual": "ручное обновление",
            "hourly": "автообновление (1 час)",
            "cbonds_credentials_updated": "автообновление после ввода Cbonds-учётных данных",
        }
        refreshed_at = st.session_state.last_refresh_at_utc.strftime("%Y-%m-%d %H:%M:%S UTC")
        refresh_label = reason_labels.get(st.session_state.last_refresh_reason, "обновление")
        st.caption(f"Последнее обновление: {refreshed_at} ({refresh_label}).")

    rates_tab, calendars_tab, mapping_tab = st.tabs(
        ["Ставки", "Календари", "Маппинг ставок"]
    )

    with rates_tab:
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
            st.caption(
                "Добавляйте/удаляйте строки в таблице напрямую и затем нажимайте «Сохранить календари»."
            )

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

    with mapping_tab:
        st.subheader("Маппинг ставок к календарям и сдвигам")
        st.caption(
            "Строки автоматически синхронизированы с источниками на вкладке «Ставки». "
            "Изменяйте только Calendar и Shift."
        )
        calendar_options = _calendar_options_for_mapping(st.session_state.rate_calendar_mapping)
        mapping_editor = st.data_editor(
            st.session_state.rate_calendar_mapping,
            num_rows="fixed",
            hide_index=True,
            use_container_width=True,
            key="rate_calendar_mapping_editor",
            column_config={
                "source_name": st.column_config.TextColumn("source_name", disabled=True),
                "Calendar": st.column_config.SelectboxColumn(
                    "Calendar", options=calendar_options, required=True
                ),
                "Shift": st.column_config.NumberColumn("Shift", step=1, format="%d"),
            },
        )
        st.session_state.rate_calendar_mapping = _sync_rate_calendar_mapping(
            mapping_editor, source_names_for_mapping
        )

        save_map_col, reload_map_col, map_hint_col = st.columns([1, 1, 2.5])
        with save_map_col:
            save_mapping = st.button(
                "Сохранить маппинг",
                type="primary",
                use_container_width=True,
                key="save_rate_mapping_button",
            )
        with reload_map_col:
            reload_mapping = st.button(
                "Перезагрузить маппинг",
                use_container_width=True,
                key="reload_rate_mapping_button",
            )
        with map_hint_col:
            st.caption(
                "Calendar выбирается из выпадающего списка доступных календарей. "
                "Shift задаётся в днях."
            )

        if save_mapping:
            validated_mapping, mapping_errors = _validate_rate_calendar_mapping(
                st.session_state.rate_calendar_mapping, source_names_for_mapping
            )
            if mapping_errors:
                st.error("Найдены ошибки в маппинге: " + "; ".join(mapping_errors[:8]))
            else:
                try:
                    _save_rate_calendar_mapping(validated_mapping)
                except OSError as exc:
                    st.error(f"Не удалось сохранить маппинг: {exc}")
                else:
                    st.session_state.rate_calendar_mapping = validated_mapping
                    st.success("Маппинг ставок сохранён.")
                    st.rerun()

        if reload_mapping:
            st.session_state.rate_calendar_mapping = _sync_rate_calendar_mapping(
                _load_rate_calendar_mapping(), source_names_for_mapping
            )
            st.success("Маппинг ставок загружен из файла.")
            st.rerun()


if __name__ == "__main__":
    main()
