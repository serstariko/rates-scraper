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


def _parse_generic_percentage(html: str) -> tuple[float | None, str | None, str]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text(" ", strip=True)
    percentages = _extract_percentages(text, limit=1)
    rate = percentages[0] if percentages else None
    rate_date = _extract_first_date(text)
    details = "Найдено автоматически по первому процентному значению."
    return rate, rate_date, details


def _parse_cbr_key_rate(html: str) -> tuple[float | None, str | None, str]:
    soup = BeautifulSoup(html, "lxml")
    table = soup.find("table")
    if not table:
        return _parse_generic_percentage(html)

    for row in table.find_all("tr"):
        cells = [cell.get_text(" ", strip=True) for cell in row.find_all(("td", "th"))]
        if len(cells) < 2:
            continue

        rate_match = re.search(r"(-?\d+(?:[.,]\d+)?)", cells[1])
        if not rate_match:
            continue

        rate_value = float(rate_match.group(1).replace(",", "."))
        date_value = _extract_first_date(cells[0])
        return rate_value, date_value, "Ключевая ставка ЦБ РФ (табличный парсер)."

    return _parse_generic_percentage(html)


def _parse_ecb_key_rates(html: str) -> tuple[float | None, str | None, str]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        if "main refinancing operations" not in line.lower():
            continue
        neighborhood = " ".join(lines[index : index + 4])
        percentages = _extract_percentages(neighborhood, limit=1)
        if percentages:
            return (
                percentages[0],
                _extract_first_date(neighborhood),
                "Основная ставка рефинансирования ЕЦБ.",
            )

    return _parse_generic_percentage(html)


def _parse_boe_bank_rate(html: str) -> tuple[float | None, str | None, str]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    for index, line in enumerate(lines):
        if "bank rate" not in line.lower():
            continue
        neighborhood = " ".join(lines[max(index - 2, 0) : index + 4])
        percentages = _extract_percentages(neighborhood, limit=1)
        if percentages:
            return percentages[0], _extract_first_date(neighborhood), "Ставка Банка Англии."

    return _parse_generic_percentage(html)


def _extract_first_global_rates_value(
    lines: list[str], date_pattern: re.Pattern[str]
) -> tuple[float | None, str | None]:
    for index, line in enumerate(lines):
        if not date_pattern.match(line):
            continue
        neighborhood = " ".join(lines[index : index + 3])
        percentages = _extract_percentages(neighborhood, limit=1)
        if percentages:
            return percentages[0], line
    return None, None


def _extract_euribor_summary_value(
    lines: list[str], date_pattern: re.Pattern[str], maturity_column: int
) -> tuple[float | None, str | None]:
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
        return None, None

    date_count = len(dates)
    percentages_text = " ".join(lines[first_date_index + date_count :])
    required_count = (maturity_column + 1) * date_count
    percentages = _extract_percentages(percentages_text, limit=max(required_count, 30))
    target_index = maturity_column * date_count
    if len(percentages) <= target_index:
        return None, None
    return percentages[target_index], dates[0]


def _parse_ester_rate(html: str) -> tuple[float | None, str | None, str]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]

    date_pattern = re.compile(r"^\d{2}-\d{2}-\d{4}$")
    for index, line in enumerate(lines):
        if not date_pattern.match(line):
            continue
        neighborhood = " ".join(lines[index : index + 3])
        percentages = _extract_percentages(neighborhood, limit=1)
        if not percentages:
            continue
        return percentages[0], line, "ESTER с global-rates.com (последнее значение)."

    return _parse_generic_percentage(html)


def _parse_euribor_rate(
    html: str, maturity_months: int, maturity_column: int
) -> tuple[float | None, str | None, str]:
    soup = BeautifulSoup(html, "lxml")
    text = soup.get_text("\n", strip=True)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    lower_text = text.lower()
    date_pattern = re.compile(r"^\d{2}-\d{2}-\d{4}$")

    maturity_page_marker = f"{maturity_months}-month euribor interest rate"
    if maturity_page_marker in lower_text:
        rate, rate_date = _extract_first_global_rates_value(lines, date_pattern)
        if rate is not None:
            return rate, rate_date, f"Euribor {maturity_months}M (страница срока)."

    summary_rate, summary_date = _extract_euribor_summary_value(lines, date_pattern, maturity_column)
    if summary_rate is not None:
        return summary_rate, summary_date, f"Euribor {maturity_months}M (сводная страница)."

    return _parse_generic_percentage(html)


def _parse_euribor_1m_rate(html: str) -> tuple[float | None, str | None, str]:
    return _parse_euribor_rate(html, maturity_months=1, maturity_column=1)


def _parse_euribor_3m_rate(html: str) -> tuple[float | None, str | None, str]:
    return _parse_euribor_rate(html, maturity_months=3, maturity_column=2)


def _parse_euribor_6m_rate(html: str) -> tuple[float | None, str | None, str]:
    return _parse_euribor_rate(html, maturity_months=6, maturity_column=3)


PARSERS: dict[str, Callable[[str], tuple[float | None, str | None, str]]] = {
    "cbr_key_rate": _parse_cbr_key_rate,
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
        rate, rate_date, details = parser(html)
        status = "ok" if rate is not None else "no_rate_found"
        error = None if rate is not None else "Процентная ставка не найдена на странице."
    except Exception as exc:  # noqa: BLE001 - возвращаем ошибку в таблицу результата
        rate = None
        rate_date = None
        details = "Ошибка при загрузке/разборе источника."
        status = "error"
        error = str(exc)

    return {
        "source_name": source.name,
        "source_url": source.url,
        "parser": source.parser,
        "rate_percent": rate,
        "rate_date": rate_date,
        "status": status,
        "details": details,
        "error": error,
        "collected_at_utc": collected_at,
    }


def scrape_all_sources(sources: list[SourceConfig]) -> pd.DataFrame:
    rows = [scrape_source(source) for source in sources]
    return pd.DataFrame(rows)
