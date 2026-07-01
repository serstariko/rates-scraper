from __future__ import annotations

from datetime import datetime, timedelta, timezone
import io
from io import BytesIO
import json
from pathlib import Path
from zoneinfo import ZoneInfo

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
MOSCOW_TZ = ZoneInfo("Europe/Moscow")
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
    cbonds_import_data: dict[str, dict[str, object]] | None = None,
    cbonds_allow_web_fetch: bool = True,
) -> None:
    with st.spinner("Идёт сбор данных..."):
        st.session_state.results = scrape_all_sources(
            source_configs,
            cbonds_credentials=cbonds_credentials,
            cbonds_import_data=cbonds_import_data,
            cbonds_allow_web_fetch=cbonds_allow_web_fetch,
        )
    st.session_state.last_refresh_at_utc = datetime.now(timezone.utc)
    st.session_state.last_refresh_reason = reason


def _format_timestamp_moscow(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        parsed = value
    else:
        text_value = str(value).strip()
        if not text_value:
            return ""
        normalized = text_value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return text_value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(MOSCOW_TZ).strftime("%d.%m.%Y %H:%M:%S")


def _table_height(row_count: int, max_height: int = 1800) -> int:
    visible_rows = max(row_count, 1)
    return min(48 + visible_rows * 35, max_height)


def _normalize_cbonds_column_name(value: str) -> str:
    return (
        value.lower()
        .replace("ё", "е")
        .replace(" ", "")
        .replace("_", "")
        .replace(".", "")
        .replace("-", "")
    )


def _extract_cbonds_import_date(value: object) -> str | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y")
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().strftime("%d.%m.%Y")
    text = str(value).strip()
    if not text:
        return None
    parsed = _format_calendar_date(text)
    return parsed


def _extract_cbonds_import_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        if isinstance(value, float) and pd.isna(value):
            return None
        return float(value)
    text = str(value).strip().replace(" ", "").replace("%", "").replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _find_cbonds_import_column(
    dataframe: pd.DataFrame, aliases: list[str]
) -> str | None:
    normalized_aliases = {_normalize_cbonds_column_name(alias) for alias in aliases}
    for column in dataframe.columns:
        normalized_column = _normalize_cbonds_column_name(str(column))
        if normalized_column in normalized_aliases:
            return column
    return None


def _parse_cbonds_import_file(
    uploaded_file,
) -> tuple[dict[str, dict[str, object]], list[str]]:
    try:
        file_name = str(uploaded_file.name).lower()
        if file_name.endswith(".csv"):
            file_bytes = uploaded_file.getvalue()
            decoded: str | None = None
            for encoding in ("utf-8-sig", "cp1251", "utf-16"):
                try:
                    decoded = file_bytes.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            if decoded is None:
                return {}, ["Не удалось прочитать CSV: неподдерживаемая кодировка."]
            dataframe = pd.read_csv(io.StringIO(decoded), sep=None, engine="python")
        else:
            dataframe = pd.read_excel(uploaded_file)
    except Exception as exc:  # noqa: BLE001
        return {}, [f"Ошибка чтения файла Cbonds: {exc}"]

    if dataframe.empty:
        return {}, ["Импорт-файл Cbonds пустой."]

    id_column = _find_cbonds_import_column(dataframe, ["ID индекса", "id индекса", "index id", "id"])
    value_column = _find_cbonds_import_column(dataframe, ["Значение", "value", "последнее значение"])
    date_column = _find_cbonds_import_column(dataframe, ["Дата", "date"])
    abs_change_column = _find_cbonds_import_column(dataframe, ["Абс. изм.", "Абс изм", "abs change"])

    if id_column is None or value_column is None or date_column is None:
        return {}, [
            "В файле не найдены обязательные колонки: ID индекса, Значение, Дата."
        ]

    parsed: dict[str, dict[str, object]] = {}
    errors: list[str] = []
    for row in dataframe.to_dict("records"):
        raw_id = row.get(id_column)
        if raw_id is None or (isinstance(raw_id, float) and pd.isna(raw_id)):
            continue
        try:
            index_id = str(int(float(str(raw_id).strip()))).strip()
        except ValueError:
            errors.append(f"Некорректный ID индекса: {raw_id}")
            continue

        current_value = _extract_cbonds_import_float(row.get(value_column))
        current_date = _extract_cbonds_import_date(row.get(date_column))
        abs_change = (
            _extract_cbonds_import_float(row.get(abs_change_column))
            if abs_change_column is not None
            else None
        )

        previous_value = None
        if current_value is not None and abs_change is not None:
            previous_value = current_value - abs_change

        parsed[index_id] = {
            "value": current_value,
            "date": current_date,
            "previous_value": previous_value,
            "previous_date": None,
        }

    if not parsed:
        errors.append("В файле нет валидных строк с ID индекса.")
    return parsed, errors


def _parse_ddmmyyyy_date(value: object) -> datetime.date | None:
    if value is None:
        return None
    text_value = str(value).strip()
    if not text_value:
        return None
    try:
        return datetime.strptime(text_value, "%d.%m.%Y").date()
    except ValueError:
        return None


def _calendar_holiday_sets_from_dataframe(
    calendars_df: pd.DataFrame,
) -> tuple[dict[str, set[datetime.date]], list[str]]:
    calendars_dict, invalid_values = _calendar_dataframe_to_dict(calendars_df)
    holiday_sets: dict[str, set[datetime.date]] = {}
    for calendar_name, values in calendars_dict.items():
        holiday_sets[calendar_name] = {
            datetime.strptime(value, "%d.%m.%Y").date() for value in values
        }
    return holiday_sets, invalid_values


def _holidays_for_calendar_expression(
    calendar_expression: str, holiday_sets: dict[str, set[datetime.date]]
) -> set[datetime.date]:
    parts = [part.strip() for part in calendar_expression.split("/") if part.strip()]
    if not parts:
        return set()

    holidays: set[datetime.date] = set()
    for part in parts:
        holidays.update(holiday_sets.get(part, set()))
    return holidays


def _is_business_day(
    day: datetime.date, calendar_expression: str, holiday_sets: dict[str, set[datetime.date]]
) -> bool:
    if day.weekday() >= 5:
        return False
    holidays = _holidays_for_calendar_expression(calendar_expression, holiday_sets)
    return day not in holidays


def _required_business_date(
    calendar_expression: str,
    shift: int,
    holiday_sets: dict[str, set[datetime.date]],
    base_date: datetime.date,
) -> datetime.date:
    candidate = base_date
    while not _is_business_day(candidate, calendar_expression, holiday_sets):
        candidate = candidate - timedelta(days=1)

    if shift == 0:
        return candidate

    direction = -1 if shift < 0 else 1
    remaining = abs(shift)
    while remaining > 0:
        candidate = candidate + timedelta(days=direction)
        if _is_business_day(candidate, calendar_expression, holiday_sets):
            remaining -= 1
    return candidate


def _mapping_lookup(mapping_df: pd.DataFrame) -> dict[str, tuple[str, int]]:
    lookup: dict[str, tuple[str, int]] = {}
    if mapping_df.empty:
        return lookup
    for row in mapping_df.to_dict("records"):
        source_name = str(row.get("source_name", "")).strip()
        if not source_name:
            continue
        calendar_value = str(row.get("Calendar", "")).strip()
        default_calendar, default_shift = _default_rate_calendar_mapping(source_name)
        if not calendar_value:
            calendar_value = default_calendar
        shift_value = _to_int_shift(row.get("Shift"), default=default_shift)
        if shift_value is None:
            shift_value = default_shift
        lookup[source_name] = (calendar_value, shift_value)
    return lookup


def _with_required_date_validation(
    results: pd.DataFrame,
    mapping_df: pd.DataFrame,
    holiday_calendars_df: pd.DataFrame,
) -> tuple[pd.DataFrame, list[str]]:
    if results.empty:
        return results.copy(), []

    holiday_sets, invalid_values = _calendar_holiday_sets_from_dataframe(holiday_calendars_df)
    mapping_by_source = _mapping_lookup(mapping_df)
    base_date = datetime.now(MOSCOW_TZ).date()

    validated = results.copy()
    required_dates: list[str | None] = []
    date_matches: list[bool | None] = []

    for row in validated.to_dict("records"):
        source_name = str(row.get("source_name", "")).strip()
        if source_name in mapping_by_source:
            calendar_expression, shift = mapping_by_source[source_name]
        else:
            calendar_expression, shift = _default_rate_calendar_mapping(source_name)

        required_date = _required_business_date(
            calendar_expression=calendar_expression,
            shift=shift,
            holiday_sets=holiday_sets,
            base_date=base_date,
        )
        actual_date = _parse_ddmmyyyy_date(row.get("rate_date"))

        required_dates.append(required_date.strftime("%d.%m.%Y"))
        date_matches.append(actual_date == required_date if actual_date is not None else False)

    validated["required_rate_date"] = required_dates
    validated["required_date_matches"] = date_matches
    return validated, invalid_values


def _style_summary_date_column(
    summary_table: pd.DataFrame, date_match_by_source: dict[str, bool | None]
):
    def _row_style(row: pd.Series) -> list[str]:
        styles = [""] * len(row.index)
        source_name = str(row.get("Источник", "")).strip()
        match_status = date_match_by_source.get(source_name)
        if match_status is False and "Дата текущей" in row.index:
            date_idx = row.index.get_loc("Дата текущей")
            styles[date_idx] = "background-color: #fecaca; color: #7f1d1d; font-weight: 600;"
        return styles

    return summary_table.style.apply(_row_style, axis=1)


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
    if "collected_at_utc" in summary.columns:
        summary["collected_at_utc"] = summary["collected_at_utc"].apply(
            _format_timestamp_moscow
        )
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
            "collected_at_utc": "Собрано (МСК)",
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
        "required_rate_date",
        "required_date_matches",
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
    technical = results[columns].copy()
    if "collected_at_utc" in technical.columns:
        technical["collected_at_utc"] = technical["collected_at_utc"].apply(
            _format_timestamp_moscow
        )
        technical = technical.rename(columns={"collected_at_utc": "collected_at_msk"})
    return technical


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
        load_cbonds_enabled = st.checkbox(
            "Загружать данные из Cbonds",
            key="load_cbonds_enabled",
            help="По умолчанию отключено. Включите, если нужно обновлять строки Cbonds.",
        )
        cbonds_import_file = st.file_uploader(
            "Импорт файла Cbonds (XLSX/XLS/CSV)",
            type=["xlsx", "xls", "csv"],
            key="cbonds_import_file",
            help=(
                "Файл должен содержать колонки ID индекса, Значение, Дата "
                "(Абс. изм. — опционально)."
            ),
        )
        cbonds_login = st.text_input(
            "Логин Cbonds",
            key="cbonds_login",
            autocomplete="username",
            help="Нужен для источников с parser=cbonds_index_rate.",
            disabled=not load_cbonds_enabled,
        )
        cbonds_password = st.text_input(
            "Пароль Cbonds",
            type="password",
            key="cbonds_password",
            autocomplete="current-password",
            disabled=not load_cbonds_enabled,
        )
        st.caption(
            "Учётные данные используются только для текущего запуска обновления и не выгружаются в результаты."
        )

    cbonds_import_data: dict[str, dict[str, object]] | None = None
    cbonds_import_errors: list[str] = []
    if cbonds_import_file is not None:
        cbonds_import_data, cbonds_import_errors = _parse_cbonds_import_file(cbonds_import_file)
        if cbonds_import_errors:
            st.warning("Импорт Cbonds: " + "; ".join(cbonds_import_errors[:4]))
        else:
            st.caption(
                f"Импорт Cbonds: загружено индексов — {len(cbonds_import_data)}."
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
    cbonds_import_available = cbonds_import_data is not None and bool(cbonds_import_data)
    if not load_cbonds_enabled and not cbonds_import_available:
        source_configs = [
            source for source in source_configs if source.parser != "cbonds_index_rate"
        ]
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

    cbonds_credentials: tuple[str, str] | None = None
    if load_cbonds_enabled:
        cbonds_login = str(cbonds_login).strip()
        cbonds_password = str(cbonds_password).strip()
        if cbonds_login and cbonds_password:
            cbonds_credentials = (cbonds_login, cbonds_password)
        elif cbonds_login or cbonds_password:
            st.warning("Для Cbonds укажите и логин, и пароль (или оставьте оба поля пустыми).")

    if (
        refresh_reason is None
        and load_cbonds_enabled
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
        _refresh_results(
            source_configs,
            refresh_reason,
            cbonds_credentials=cbonds_credentials,
            cbonds_import_data=cbonds_import_data,
            cbonds_allow_web_fetch=load_cbonds_enabled,
        )
        st.success(f"Собрано источников: {len(st.session_state.results)}")

    st.session_state.last_auto_tick = auto_tick

    if st.session_state.last_refresh_at_utc is not None:
        reason_labels = {
            "initial": "первичная загрузка",
            "manual": "ручное обновление",
            "hourly": "автообновление (1 час)",
            "cbonds_credentials_updated": "автообновление после ввода Cbonds-учётных данных",
        }
        refreshed_at = _format_timestamp_moscow(st.session_state.last_refresh_at_utc)
        refresh_label = reason_labels.get(st.session_state.last_refresh_reason, "обновление")
        st.caption(f"Последнее обновление: {refreshed_at} МСК ({refresh_label}).")

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

            validated_results, invalid_calendar_values = _with_required_date_validation(
                filtered_results,
                st.session_state.rate_calendar_mapping,
                st.session_state.holiday_calendars,
            )
            if invalid_calendar_values:
                invalid_preview = ", ".join(invalid_calendar_values[:6])
                if len(invalid_calendar_values) > 6:
                    invalid_preview += ", ..."
                st.warning(
                    "Некоторые праздничные даты в календарях имеют неверный формат и не участвуют в валидации: "
                    f"{invalid_preview}"
                )

            summary_table = _build_summary_results_table(validated_results)
            technical_table = _build_technical_results_table(validated_results)
            date_match_by_source = {
                str(row.get("source_name", "")): row.get("required_date_matches")
                for row in validated_results.to_dict("records")
            }

            summary_tab, technical_tab = st.tabs(["Основная таблица", "Технические детали"])
            with summary_tab:
                styled_summary = _style_summary_date_column(summary_table, date_match_by_source)
                st.dataframe(
                    styled_summary,
                    use_container_width=True,
                    hide_index=True,
                    height=_table_height(len(summary_table)),
                    column_config={
                        "Текущая ставка": st.column_config.NumberColumn(format="%.4f"),
                        "Предыдущая ставка": st.column_config.NumberColumn(format="%.4f"),
                        "Изменение (абс.)": st.column_config.NumberColumn(format="%.4f"),
                        "Изменение (%)": st.column_config.NumberColumn(format="%.4f"),
                    },
                )
            with technical_tab:
                st.dataframe(
                    technical_table,
                    use_container_width=True,
                    hide_index=True,
                    height=_table_height(len(technical_table), max_height=2200),
                )

            st.download_button(
                label="Скачать Excel",
                data=_to_excel_bytes(results),
                file_name=f"OTC_MD_{datetime.now(MOSCOW_TZ).strftime('%d %m %Y')}.xlsx",
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
            height=_table_height(len(st.session_state.holiday_calendars), max_height=1400),
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
            height=_table_height(len(st.session_state.rate_calendar_mapping), max_height=1800),
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
