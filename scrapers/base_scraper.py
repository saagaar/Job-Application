from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Optional

import requests
from bs4 import BeautifulSoup

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-AU,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class BaseScraper(ABC):
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)

    @abstractmethod
    def search(self, role: str, location: str = "Australia", max_results: int = 50) -> list[dict]:
        """Return list of raw job dicts: title, company, url, description, location, salary_range, source."""

    def _fetch_page(self, url: str, retries: int = 3, delay: float = 1.5) -> Optional[BeautifulSoup]:
        for attempt in range(retries):
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code == 200:
                    return BeautifulSoup(resp.text, "lxml")
                if resp.status_code in (429, 503):
                    time.sleep(delay * (2 ** attempt))
                    continue
                return None
            except requests.RequestException:
                if attempt < retries - 1:
                    time.sleep(delay)
        return None

    def _text(self, soup: BeautifulSoup, selector: str, default: str = "") -> str:
        try:
            el = soup.select_one(selector)
            return el.get_text(separator=" ", strip=True) if el else default
        except Exception:
            return default
