from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
from typing import Callable

import pandas as pd
import requests
from bs4 import BeautifulSoup

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)


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
    response = requests.get(
        url,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8"},
    )
    response.raise_for_status()
    return response.text


def scrape_source(source: SourceConfig) -> dict[str, str | float | None]:
    collected_at = datetime.utcnow().replace(microsecond=0).isoformat() + "Z"
    parser = PARSERS.get(source.parser, PARSERS["generic"])

    try:
        html = fetch_html(source.url)
        parsed = parser(html)
        current_rate = parsed.current_rate
        current_date = parsed.current_date
        previous_rate = parsed.previous_rate
        previous_date = parsed.previous_date

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
