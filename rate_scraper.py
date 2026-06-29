from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import json
import re
from typing import Callable
import csv
from io import StringIO
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
MOEX_ISS_INDEX_SECIDS = {
    "rusfar_rate": "RUSFAR",
    "rusfar3m_rate": "RUSFAR3M",
    "rusfarcny_rate": "RUSFARCNY",
    "oisfx_rate": "OISFIXUSD",
}
NFEASWAP_TENOR_PARSERS = {
    "nfeaswap_1w_rate": "1W",
    "nfeaswap_2w_rate": "2W",
    "nfeaswap_1m_rate": "1M",
    "nfeaswap_2m_rate": "2M",
    "nfeaswap_3m_rate": "3M",
    "nfeaswap_6m_rate": "6M",
    "nfeaswap_9m_rate": "9M",
    "nfeaswap_1y_rate": "1Y",
}
CME_SOFR_SWAP_DIRECT_TENOR_PARSERS = {
    "cme_sofr_swap_1y_rate": "1 Year",
    "cme_sofr_swap_2y_rate": "2 Year",
    "cme_sofr_swap_3y_rate": "3 Year",
    "cme_sofr_swap_5y_rate": "5 Year",
    "cme_sofr_swap_10y_rate": "10 Year",
}
CME_SOFR_SWAP_INTERPOLATED_TENOR_PARSERS = {
    "cme_sofr_swap_4y_interp_rate": 4,
    "cme_sofr_swap_6y_interp_rate": 6,
    "cme_sofr_swap_7y_interp_rate": 7,
    "cme_sofr_swap_8y_interp_rate": 8,
    "cme_sofr_swap_9y_interp_rate": 9,
}
SOFR_MARKETS_API_URL = (
    "https://markets.newyorkfed.org/read"
    "?productCode=50&eventCodes=520&startPosition=0&limit=5"
)
CHINAMONEY_FRR_JSON_URL = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/frr.json"
CHINAMONEY_FRR_HISTORY_CSV_URL = "https://www.chinamoney.com.cn/r/cms/www/chinamoney/data/currency/frr-chrt.csv"
CME_BLOCK_MESSAGE_FRAGMENT = "This IP address is blocked due to suspected web scraping activity"
CME_SOFR_CACHE_PATH = Path(__file__).resolve().parent / ".cme_sofr_swaps_cache.json"


@dataclass(slots=True)
class SourceConfig:
    name: str
    url: str
    parser: str


@dataclass(slots=True)
class ParsedRate:
    current_rate: float | None
    current_date: str | None
    previous_rate: float | None
    previous_date: str | None
    details: str


def _extract_first_date(text: str) -> str | None:
    patterns = (
        r"\b\d{2}\.\d{2}\.\d{4}\b",
        r"\b\d{4}-\d{2}-\d{2}\b",
        r"\b\d{2}-\d{2}-\d{4}\b",
        r"\b\d{2}/\d{2}/\d{4}\b",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def _format_date_ddmmyyyy(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None

    known_formats = (
        "%d.%m.%Y",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%m-%d-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d %b %Y",
    )
    for date_format in known_formats:
        try:
            parsed = datetime.strptime(cleaned, date_format)
            return parsed.strftime("%d.%m.%Y")
        except ValueError:
            continue
    return cleaned


def _extract_percentages(text: str, limit: int = 5) -> list[float]:
    values: list[float] = []
    for match in re.finditer(r"(-?\d+(?:[.,]\d+)?)\s*%", text):
        normalized = match.group(1).replace(",", ".")
        try:
            values.append(float(normalized))
        except ValueError:
            continue
        if len(values) >= limit:
            break
    return values


def _extract_rate_date_pairs(lines: list[str], max_pairs: int = 2) -> list[tuple[float, str]]:
    pairs: list[tuple[float, str]] = []
    for index, line in enumerate(lines):
        date_value = _extract_first_date(line)
        if not date_value:
            continue

        neighborhood = " ".join(lines[index : index + 4])
        percentages = _extract_percentages(neighborhood, limit=1)
        if not percentages:
            continue
        pairs.append((percentages[0], date_value))
        if len(pairs) >= max_pairs:
            break
    return pairs


def _build_parsed_rate(
    current_rate: float | None,
    current_date: str | None,
    details: str,
    previous_rate: float | None = None,
    previous_date: str | None = None,
) -> ParsedRate:
    return ParsedRate(
        current_rate=current_rate,
        current_date=current_date,
        previous_rate=previous_rate,
        previous_date=previous_date,
        details=details,
    )


def _parse_generic_percentage(html: str) -> ParsedRate:
    soup = BeautifulSoup(html, "lxml")
    lines = [line.strip() for line in soup.get_text("\n", strip=True).splitlines() if line.strip()]
    text = " ".join(lines)
    pairs = _extract_rate_date_pairs(lines, max_pairs=2)

    rate = pairs[0][0] if pairs else None
    rate_date = pairs[0][1] if pairs else _extract_first_date(text)
    previous_rate = pairs[1][0] if len(pairs) > 1 else None
    previous_date = pairs[1][1] if len(pairs) > 1 else None

    if rate is None:
        percentages = _extract_percentages(text, limit=2)
        if percentages:
            rate = percentages[0]
        if len(percentages) > 1:
            previous_rate = percentages[1]

    details = "Найдено автоматически по первому процентному значению."
    return _build_parsed_rate(
        current_rate=rate,
        current_date=rate_date,
        previous_rate=previous_rate,
        previous_date=previous_date,
        details=details,
    )


def _parse_cbr_key_rate(html: str) -> ParsedRate:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return _parse_generic_percentage(html)

    series: list[tuple[float, str | None]] = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(("td", "th"))]
        if len(cells) < 2:
            continue

        rate_match = re.search(r"(-?\d+(?:[.,]\d+)?)", cells[1])
        if not rate_match:
            continue

        rate_value = float(rate_match.group(1).replace(",", "."))
        date_value = _extract_first_date(cells[0])
        series.append((rate_value, date_value))
        if len(series) >= 2:
            break

    if series:
        previous_rate = series[1][0] if len(series) > 1 else None
        previous_date = series[1][1] if len(series) > 1 else None
        return _build_parsed_rate(
            current_rate=series[0][0],
            current_date=series[0][1],
            previous_rate=previous_rate,
            previous_date=previous_date,
            details="Ключевая ставка ЦБ РФ (табличный парсер).",
        )

    return _parse_generic_percentage(html)


def _parse_ecb_key_rates(html: str) -> ParsedRate:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        if "main refinancing operations" not in line.lower():
            continue
        neighborhood = " ".join(lines[index : index + 4])
        percentages = _extract_percentages(neighborhood, limit=1)
        if percentages:
            return _build_parsed_rate(
                current_rate=percentages[0],
                current_date=_extract_first_date(neighborhood),
                previous_rate=None,
                previous_date=None,
                details="Основная ставка рефинансирования ЕЦБ.",
            )

    return _parse_generic_percentage(html)


def _parse_boe_bank_rate(html: str) -> ParsedRate:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        if "bank rate" not in line.lower():
            continue
        neighborhood = " ".join(lines[max(index - 2, 0) : index + 4])
        percentages = _extract_percentages(neighborhood, limit=1)
        if percentages:
            return _build_parsed_rate(
                current_rate=percentages[0],
                current_date=_extract_first_date(neighborhood),
                previous_rate=None,
                previous_date=None,
                details="Ставка Банка Англии.",
            )

    return _parse_generic_percentage(html)


def _parse_ruonia_rate(html: str) -> ParsedRate:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return _parse_generic_percentage(html)

    rows: list[list[str]] = []
    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(("td", "th"))]
        if cells:
            rows.append(cells)

    if not rows:
        return _parse_generic_percentage(html)

    date_row: list[str] | None = None
    rate_row: list[str] | None = None

    for row in rows:
        label = row[0].lower()
        if "дата ставки" in label:
            date_row = row
        if "ставка ruonia" in label:
            rate_row = row

    if not date_row or not rate_row:
        return _parse_generic_percentage(html)

    dates = []
    for cell in date_row[1:]:
        parsed_date = _extract_first_date(cell)
        if parsed_date:
            dates.append(parsed_date)

    rates = []
    for cell in rate_row[1:]:
        match = re.search(r"-?\d+(?:[.,]\d+)?", cell)
        if not match:
            continue
        rates.append(float(match.group(0).replace(",", ".")))

    if not dates or not rates:
        return _parse_generic_percentage(html)

    max_index = min(len(dates), len(rates)) - 1
    previous_index = max_index - 1
    previous_rate = rates[previous_index] if previous_index >= 0 else None
    previous_date = dates[previous_index] if previous_index >= 0 else None
    return _build_parsed_rate(
        current_rate=rates[max_index],
        current_date=dates[max_index],
        previous_rate=previous_rate,
        previous_date=previous_date,
        details="Ставка RUONIA ЦБ РФ (табличный парсер).",
    )


def _extract_global_rates_pairs(
    lines: list[str], date_pattern: re.Pattern[str], max_pairs: int = 2
) -> list[tuple[float, str]]:
    pairs: list[tuple[float, str]] = []
    for index, line in enumerate(lines):
        if not date_pattern.match(line):
            continue
        neighborhood = " ".join(lines[index : index + 3])
        percentages = _extract_percentages(neighborhood, limit=1)
        if percentages:
            pairs.append((percentages[0], line))
            if len(pairs) >= max_pairs:
                break
    return pairs


def _extract_euribor_summary_values(
    lines: list[str], date_pattern: re.Pattern[str], maturity_column: int, max_pairs: int = 2
) -> list[tuple[float, str]]:
    dates: list[str] = []
    first_date_index: int | None = None
    for index, line in enumerate(lines):
        if date_pattern.match(line):
            if first_date_index is None:
                first_date_index = index
            dates.append(line)
            continue
        if dates:
            break

    if not dates or first_date_index is None:
        return []

    date_count = len(dates)
    percentages_text = " ".join(lines[first_date_index + date_count :])
    required_count = (maturity_column + 1) * date_count
    percentages = _extract_percentages(percentages_text, limit=max(required_count + date_count, 30))
    target_start = maturity_column * date_count
    target_end = target_start + date_count
    selected_rates = percentages[target_start:target_end]

    pairs: list[tuple[float, str]] = []
    pair_count = min(len(selected_rates), len(dates), max_pairs)
    for idx in range(pair_count):
        pairs.append((selected_rates[idx], dates[idx]))
    return pairs


def _parse_ester_rate(html: str) -> ParsedRate:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    date_pattern = re.compile(r"^\d{2}-\d{2}-\d{4}$")
    pairs = _extract_global_rates_pairs(lines, date_pattern, max_pairs=2)
    if pairs:
        previous_rate = pairs[1][0] if len(pairs) > 1 else None
        previous_date = pairs[1][1] if len(pairs) > 1 else None
        return _build_parsed_rate(
            current_rate=pairs[0][0],
            current_date=pairs[0][1],
            previous_rate=previous_rate,
            previous_date=previous_date,
            details="ESTER с global-rates.com (последнее значение).",
        )

    return _parse_generic_percentage(html)


def _parse_euribor_rate(
    html: str, maturity_months: int, maturity_column: int
) -> ParsedRate:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lower_text = text.lower()
    date_pattern = re.compile(r"^\d{2}-\d{2}-\d{4}$")

    maturity_page_marker = f"{maturity_months}-month euribor interest rate"
    if maturity_page_marker in lower_text:
        pairs = _extract_global_rates_pairs(lines, date_pattern, max_pairs=2)
        if pairs:
            previous_rate = pairs[1][0] if len(pairs) > 1 else None
            previous_date = pairs[1][1] if len(pairs) > 1 else None
            return _build_parsed_rate(
                current_rate=pairs[0][0],
                current_date=pairs[0][1],
                previous_rate=previous_rate,
                previous_date=previous_date,
                details=f"Euribor {maturity_months}M (страница срока).",
            )

    summary_pairs = _extract_euribor_summary_values(lines, date_pattern, maturity_column, max_pairs=2)
    if summary_pairs:
        previous_rate = summary_pairs[1][0] if len(summary_pairs) > 1 else None
        previous_date = summary_pairs[1][1] if len(summary_pairs) > 1 else None
        return _build_parsed_rate(
            current_rate=summary_pairs[0][0],
            current_date=summary_pairs[0][1],
            previous_rate=previous_rate,
            previous_date=previous_date,
            details=f"Euribor {maturity_months}M (сводная страница).",
        )

    return _parse_generic_percentage(html)


def _parse_euribor_1m_rate(html: str) -> ParsedRate:
    return _parse_euribor_rate(html, maturity_months=1, maturity_column=1)


def _parse_euribor_3m_rate(html: str) -> ParsedRate:
    return _parse_euribor_rate(html, maturity_months=3, maturity_column=2)


def _parse_euribor_6m_rate(html: str) -> ParsedRate:
    return _parse_euribor_rate(html, maturity_months=6, maturity_column=3)


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        normalized = value.strip().replace(",", ".")
        if not normalized:
            return None
        try:
            return float(normalized)
        except ValueError:
            return None
    return None


def _parse_moex_iss_rate(secid: str) -> ParsedRate:
    market_url = (
        "https://iss.moex.com/iss/engines/stock/markets/index/securities/"
        f"{secid}.json?iss.meta=off&iss.only=marketdata"
        "&marketdata.columns=SECID,TRADEDATE,CURRENTVALUE,LASTVALUE,UPDATETIME"
    )
    history_url = (
        "https://iss.moex.com/iss/history/engines/stock/markets/index/securities/"
        f"{secid}.json?iss.meta=off&history.columns=TRADEDATE,CLOSE&sort_order=desc&start=0&limit=20"
    )

    market_json = json.loads(fetch_html(market_url))
    market_data = market_json.get("marketdata", {})
    market_columns = market_data.get("columns", [])
    market_rows = market_data.get("data", [])

    current_rate: float | None = None
    current_date: str | None = None
    if market_rows:
        market_row = dict(zip(market_columns, market_rows[0]))
        current_rate = _to_float(market_row.get("CURRENTVALUE"))
        if current_rate is None:
            current_rate = _to_float(market_row.get("LASTVALUE"))
        current_date = market_row.get("TRADEDATE")

    history_json = json.loads(fetch_html(history_url))
    history_data = history_json.get("history", {})
    history_columns = history_data.get("columns", [])
    history_rows = history_data.get("data", [])

    history_points: list[tuple[str, float]] = []
    for row in history_rows:
        parsed_row = dict(zip(history_columns, row))
        trade_date = parsed_row.get("TRADEDATE")
        close_value = _to_float(parsed_row.get("CLOSE"))
        if isinstance(trade_date, str) and close_value is not None:
            history_points.append((trade_date, close_value))

    if current_date is None and history_points:
        current_date = history_points[0][0]
    if current_rate is None and history_points:
        current_rate = history_points[0][1]

    previous_rate: float | None = None
    previous_date: str | None = None
    for trade_date, close_value in history_points:
        if current_date is not None and trade_date == current_date:
            continue
        previous_date = trade_date
        previous_rate = close_value
        break

    return _build_parsed_rate(
        current_rate=current_rate,
        current_date=current_date,
        previous_rate=previous_rate,
        previous_date=previous_date,
        details=f"MOEX ISS индекс {secid} (CURRENTVALUE + history CLOSE).",
    )


def _parse_sofr_rate() -> ParsedRate:
    payload = json.loads(fetch_html(SOFR_MARKETS_API_URL))
    rows = payload.get("data", [])

    points: list[tuple[str, float]] = []
    for row in rows:
        if row.get("eventDescription") != "SOFR":
            continue

        raw_data = row.get("data")
        if isinstance(raw_data, str):
            try:
                parsed_data = json.loads(raw_data)
            except json.JSONDecodeError:
                continue
        elif isinstance(raw_data, dict):
            parsed_data = raw_data
        else:
            continue

        rate = _to_float(parsed_data.get("dailyRate"))
        rate_date = parsed_data.get("refRateDt") or row.get("postDt")
        if rate is None or not isinstance(rate_date, str):
            continue

        points.append((rate_date, rate))
        if len(points) >= 2:
            break

    current_rate = points[0][1] if points else None
    current_date = points[0][0] if points else None
    previous_rate = points[1][1] if len(points) > 1 else None
    previous_date = points[1][0] if len(points) > 1 else None

    return _build_parsed_rate(
        current_rate=current_rate,
        current_date=current_date,
        previous_rate=previous_rate,
        previous_date=previous_date,
        details="NY Fed Markets API: SOFR dailyRate.",
    )


def _parse_fr007_rate() -> ParsedRate:
    csv_text = fetch_html(CHINAMONEY_FRR_HISTORY_CSV_URL)
    reader = csv.reader(StringIO(csv_text))

    history_points: list[tuple[str, float]] = []
    for row in reader:
        if not row:
            continue
        date_value = row[0].strip()
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
            continue
        if len(row) <= 7:
            continue

        rate_value = _to_float(row[7].strip())
        if rate_value is None:
            continue
        history_points.append((date_value, rate_value))
        if len(history_points) >= 3:
            break

    current_rate = history_points[0][1] if history_points else None
    current_date = history_points[0][0] if history_points else None
    previous_rate = history_points[1][1] if len(history_points) > 1 else None
    previous_date = history_points[1][0] if len(history_points) > 1 else None

    if current_rate is None:
        json_payload = json.loads(fetch_html(CHINAMONEY_FRR_JSON_URL))
        for record in json_payload.get("records", []):
            if record.get("productCode") != "FR007":
                continue
            current_rate = _to_float(record.get("value"))
            produce_date = record.get("produceDate")
            if isinstance(produce_date, str):
                current_date = produce_date
            break

    return _build_parsed_rate(
        current_rate=current_rate,
        current_date=current_date,
        previous_rate=previous_rate,
        previous_date=previous_date,
        details="ChinaMoney FR007 (frr-chrt.csv, fallback: frr.json).",
    )


def _build_nfeaswap_archive_csv_url(days_back: int = 45) -> str:
    date_to = datetime.utcnow().date()
    date_from = date_to - timedelta(days=days_back)
    return (
        "https://nfeaswap.ru/archive"
        f"?date_from={date_from.strftime('%d-%m-%Y')}"
        f"&date_to={date_to.strftime('%d-%m-%Y')}"
        "&format=csv"
    )


def _normalize_nfeaswap_date(value: str) -> str | None:
    cleaned = value.strip().strip('"')
    try:
        parsed = datetime.strptime(cleaned, "%d-%m-%Y")
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%d")


def _parse_nfeaswap_tenor(tenor: str) -> ParsedRate:
    csv_text = fetch_html(_build_nfeaswap_archive_csv_url())
    reader = csv.reader(StringIO(csv_text), delimiter=";", quotechar='"')
    rows = [row for row in reader if row]
    if len(rows) < 3:
        return _build_parsed_rate(
            current_rate=None,
            current_date=None,
            previous_rate=None,
            previous_date=None,
            details=f"NFEASWAP архив CSV: недостаточно данных для {tenor}.",
        )

    header = [cell.strip().strip('"').upper() for cell in rows[1]]
    if tenor not in header:
        return _build_parsed_rate(
            current_rate=None,
            current_date=None,
            previous_rate=None,
            previous_date=None,
            details=f"NFEASWAP архив CSV: срок {tenor} не найден в заголовке.",
        )
    tenor_index = header.index(tenor)

    points: list[tuple[str, float]] = []
    for row in rows[2:]:
        if len(row) <= tenor_index:
            continue
        rate_date = _normalize_nfeaswap_date(row[0])
        rate_value = _to_float(row[tenor_index].replace("--", "").strip())
        if rate_date is None or rate_value is None:
            continue
        points.append((rate_date, rate_value))
        if len(points) >= 2:
            break

    current_rate = points[0][1] if points else None
    current_date = points[0][0] if points else None
    previous_rate = points[1][1] if len(points) > 1 else None
    previous_date = points[1][0] if len(points) > 1 else None

    return _build_parsed_rate(
        current_rate=current_rate,
        current_date=current_date,
        previous_rate=previous_rate,
        previous_date=previous_date,
        details=f"NFEASWAP архив CSV: срок {tenor}.",
    )


def _cme_proxy_url(url: str) -> str:
    normalized = url
    if normalized.startswith("https://"):
        normalized = normalized[len("https://") :]
    elif normalized.startswith("http://"):
        normalized = normalized[len("http://") :]
    return f"https://r.jina.ai/http://{normalized}"


def _normalize_cme_trade_date(raw_date: str | None) -> str | None:
    if raw_date is None:
        return None
    cleaned = raw_date.strip()
    if not cleaned:
        return None
    try:
        parsed = datetime.strptime(cleaned, "%d %b %Y")
    except ValueError:
        return None
    return parsed.strftime("%Y-%m-%d")


def _clean_cme_rate_text(value: str) -> str:
    return value.replace(" ", "").replace(",", ".").strip()


def _extract_cme_sofr_rows(page_text: str) -> dict[str, float]:
    rows: dict[str, float] = {}

    for line in page_text.splitlines():
        row_match = re.match(
            r"^\|\s*(\d+\s+Year)\s*\|\s*([0-9.,\s-]+)\s*\|\s*([0-9.,\s-]+)\s*\|$",
            line.strip(),
        )
        if not row_match:
            continue
        tenor = row_match.group(1)
        rate_text = _clean_cme_rate_text(row_match.group(2))
        try:
            rows[tenor] = float(rate_text)
        except ValueError:
            continue

    if rows:
        return rows

    soup = BeautifulSoup(page_text, "lxml")
    for row in soup.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(("td", "th"))]
        if len(cells) < 2:
            continue
        tenor_text = cells[0]
        if not re.fullmatch(r"\d+\s+Year", tenor_text):
            continue
        rate_text = _clean_cme_rate_text(cells[1])
        try:
            rows[tenor_text] = float(rate_text)
        except ValueError:
            continue
    return rows


def _extract_cme_trade_date(page_text: str) -> str | None:
    markdown_match = re.search(r"Trade Date:\s*([^\n]+)", page_text)
    if markdown_match:
        normalized = _normalize_cme_trade_date(markdown_match.group(1))
        if normalized:
            return normalized

    soup = BeautifulSoup(page_text, "lxml")
    body_text = soup.get_text("\n", strip=True)
    html_match = re.search(r"Trade Date:\s*([^\n]+)", body_text)
    if html_match:
        return _normalize_cme_trade_date(html_match.group(1))
    return None


def _extract_cme_year_from_tenor_label(tenor_label: str) -> int | None:
    match = re.fullmatch(r"(\d+)\s+Year", tenor_label.strip())
    if not match:
        return None
    return int(match.group(1))


def _fetch_cme_sofr_curve(source_url: str) -> tuple[str | None, dict[int, float]]:
    try:
        page_text = fetch_html(source_url)
    except Exception:  # noqa: BLE001 - fallback на прокси при блокировке/ошибках CME
        page_text = fetch_html(_cme_proxy_url(source_url))

    if CME_BLOCK_MESSAGE_FRAGMENT in page_text or page_text.strip().startswith('{"message":'):
        page_text = fetch_html(_cme_proxy_url(source_url))

    trade_date = _extract_cme_trade_date(page_text)
    tenor_rows = _extract_cme_sofr_rows(page_text)

    curve_by_year: dict[int, float] = {}
    for tenor_label, rate in tenor_rows.items():
        tenor_year = _extract_cme_year_from_tenor_label(tenor_label)
        if tenor_year is None:
            continue
        curve_by_year[tenor_year] = rate
    return trade_date, curve_by_year


def _load_cme_sofr_cache() -> dict[str, dict[str, str | float]]:
    try:
        cache_text = CME_SOFR_CACHE_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError:
        return {}
    try:
        parsed = json.loads(cache_text)
    except json.JSONDecodeError:
        return {}
    if isinstance(parsed, dict):
        return parsed
    return {}


def _save_cme_sofr_cache(cache: dict[str, dict[str, str | float]]) -> None:
    try:
        CME_SOFR_CACHE_PATH.write_text(
            json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError:
        return


def _get_cme_cached_previous(
    cache: dict[str, dict[str, str | float]], cache_key: str, trade_date: str | None
) -> tuple[float | None, str | None]:
    cached = cache.get(cache_key, {})
    cached_current_rate = _to_float(cached.get("current_rate"))
    cached_current_date = cached.get("current_date")
    current_date_value = cached_current_date if isinstance(cached_current_date, str) else None

    cached_previous_rate = _to_float(cached.get("previous_rate"))
    cached_previous_date = cached.get("previous_date")
    previous_date_value = cached_previous_date if isinstance(cached_previous_date, str) else None

    if (
        trade_date is not None
        and current_date_value is not None
        and current_date_value != trade_date
        and cached_current_rate is not None
    ):
        return cached_current_rate, current_date_value
    return cached_previous_rate, previous_date_value


def _update_cme_cache(
    cache: dict[str, dict[str, str | float]],
    cache_key: str,
    current_rate: float | None,
    trade_date: str | None,
    previous_rate: float | None,
    previous_date: str | None,
) -> None:
    if current_rate is None or trade_date is None:
        return
    cache[cache_key] = {
        "current_rate": current_rate,
        "current_date": trade_date,
        "previous_rate": previous_rate,
        "previous_date": previous_date,
    }
    _save_cme_sofr_cache(cache)


def _parse_cme_sofr_swap_tenor(tenor: str, source_url: str) -> ParsedRate:
    tenor_year = _extract_cme_year_from_tenor_label(tenor)
    if tenor_year is None:
        return _build_parsed_rate(
            current_rate=None,
            current_date=None,
            previous_rate=None,
            previous_date=None,
            details=f"CME Cleared SOFR Swaps: неизвестный срок {tenor}.",
        )

    trade_date, curve_by_year = _fetch_cme_sofr_curve(source_url)
    current_rate = curve_by_year.get(tenor_year)
    cache = _load_cme_sofr_cache()
    cache_key = f"spot:{tenor_year}Y"
    previous_rate, previous_date = _get_cme_cached_previous(cache, cache_key, trade_date)
    _update_cme_cache(cache, cache_key, current_rate, trade_date, previous_rate, previous_date)

    return _build_parsed_rate(
        current_rate=current_rate,
        current_date=trade_date,
        previous_rate=previous_rate,
        previous_date=previous_date,
        details=(
            f"CME Cleared SOFR Swaps ({tenor}) через страницу SOFR OIS Curve; "
            "предыдущее значение берётся из предыдущего успешного опроса."
        ),
    )


def _parse_cme_sofr_swap_interpolated_tenor(target_year: int, source_url: str) -> ParsedRate:
    trade_date, curve_by_year = _fetch_cme_sofr_curve(source_url)

    current_rate: float | None = None
    interpolation_details = "недостаточно точек для интерполяции"

    if target_year in curve_by_year:
        current_rate = curve_by_year[target_year]
        interpolation_details = "использована фактическая ставка из кривой"
    else:
        lower_years = sorted(year for year in curve_by_year if year < target_year)
        upper_years = sorted(year for year in curve_by_year if year > target_year)
        if lower_years and upper_years:
            lower_year = lower_years[-1]
            upper_year = upper_years[0]
            lower_rate = curve_by_year[lower_year]
            upper_rate = curve_by_year[upper_year]
            slope = (upper_rate - lower_rate) / (upper_year - lower_year)
            current_rate = lower_rate + slope * (target_year - lower_year)
            interpolation_details = (
                f"линейная интерполяция между {lower_year}Y ({lower_rate:.4f}) "
                f"и {upper_year}Y ({upper_rate:.4f})"
            )

    cache = _load_cme_sofr_cache()
    cache_key = f"interp:{target_year}Y"
    previous_rate, previous_date = _get_cme_cached_previous(cache, cache_key, trade_date)
    _update_cme_cache(cache, cache_key, current_rate, trade_date, previous_rate, previous_date)

    return _build_parsed_rate(
        current_rate=current_rate,
        current_date=trade_date,
        previous_rate=previous_rate,
        previous_date=previous_date,
        details=(
            f"CME Cleared SOFR Swaps ({target_year}Y, расчетное); {interpolation_details}; "
            "предыдущее значение берётся из предыдущего успешного опроса."
        ),
    )


PARSERS: dict[str, Callable[[str], ParsedRate]] = {
    "cbr_key_rate": _parse_cbr_key_rate,
    "ruonia_rate": _parse_ruonia_rate,
    "ecb_key_rates": _parse_ecb_key_rates,
    "boe_bank_rate": _parse_boe_bank_rate,
    "ester_rate": _parse_ester_rate,
    "euribor_1m_rate": _parse_euribor_1m_rate,
    "euribor_3m_rate": _parse_euribor_3m_rate,
    "euribor_6m_rate": _parse_euribor_6m_rate,
    "generic": _parse_generic_percentage,
}


def fetch_html(url: str, timeout: int = 25) -> str:
    session = requests.Session()
    retry_policy = Retry(
        total=3,
        connect=3,
        read=3,
        status=3,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET", "HEAD", "OPTIONS"}),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry_policy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    try:
        response = session.get(
            url,
            timeout=timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"},
        )
        response.raise_for_status()
        return response.text
    finally:
        session.close()


def scrape_source(source: SourceConfig) -> dict[str, str | float | None]:
    collected_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    parser = PARSERS.get(source.parser, PARSERS["generic"])

    try:
        if source.parser in MOEX_ISS_INDEX_SECIDS:
            parsed = _parse_moex_iss_rate(MOEX_ISS_INDEX_SECIDS[source.parser])
        elif source.parser in NFEASWAP_TENOR_PARSERS:
            parsed = _parse_nfeaswap_tenor(NFEASWAP_TENOR_PARSERS[source.parser])
        elif source.parser in CME_SOFR_SWAP_DIRECT_TENOR_PARSERS:
            parsed = _parse_cme_sofr_swap_tenor(
                CME_SOFR_SWAP_DIRECT_TENOR_PARSERS[source.parser], source.url
            )
        elif source.parser in CME_SOFR_SWAP_INTERPOLATED_TENOR_PARSERS:
            parsed = _parse_cme_sofr_swap_interpolated_tenor(
                CME_SOFR_SWAP_INTERPOLATED_TENOR_PARSERS[source.parser], source.url
            )
        elif source.parser == "sofr_rate":
            parsed = _parse_sofr_rate()
        elif source.parser == "fr007_rate":
            parsed = _parse_fr007_rate()
        else:
            html = fetch_html(source.url)
            parsed = parser(html)
        current_rate = parsed.current_rate
        current_date = _format_date_ddmmyyyy(parsed.current_date)
        previous_rate = parsed.previous_rate
        previous_date = _format_date_ddmmyyyy(parsed.previous_date)

        absolute_change = None
        relative_change = None
        if current_rate is not None and previous_rate is not None:
            absolute_change = current_rate - previous_rate
            if previous_rate != 0:
                relative_change = (absolute_change / previous_rate) * 100

        status = "ok" if current_rate is not None else "no_rate_found"
        error = None if current_rate is not None else "Процентная ставка не найдена на странице."
    except Exception as exc:  # noqa: BLE001 - возвращаем ошибку в таблицу результата
        current_rate = None
        current_date = None
        previous_rate = None
        previous_date = None
        absolute_change = None
        relative_change = None
        details = "Ошибка при загрузке/разборе источника."
        status = "error"
        error = str(exc)
    else:
        details = parsed.details

    return {
        "source_name": source.name,
        "source_url": source.url,
        "parser": source.parser,
        "rate_percent": current_rate,
        "rate_date": current_date,
        "previous_rate_percent": previous_rate,
        "previous_rate_date": previous_date,
        "relative_change_percent": relative_change,
        "absolute_change_percent": absolute_change,
        "status": status,
        "details": details,
        "error": error,
        "collected_at_utc": collected_at,
    }


def scrape_all_sources(sources: list[SourceConfig]) -> pd.DataFrame:
    rows = [scrape_source(source) for source in sources]
    return pd.DataFrame(rows)
