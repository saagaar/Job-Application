from __future__ import annotations

import json
import random
import time
from typing import Optional

from bs4 import BeautifulSoup
from rich.console import Console

from scrapers.base_scraper import BaseScraper

console = Console()

PUBLIC_SEARCH = (
    "https://www.linkedin.com/jobs/search/?keywords={role}&location={location}"
    "&f_TPR=r604800"  # last 7 days
)


class LinkedInScraper(BaseScraper):
    SOURCE = "linkedin"

    def __init__(self, li_at_cookie: Optional[str] = None):
        super().__init__()
        self._li_at = li_at_cookie

    def search(self, role: str, location: str = "Australia", max_results: int = 25) -> list[dict]:
        # Tier 1: unauthenticated requests + JSON-LD
        results = self._search_public(role, location, max_results)
        if results:
            return results

        # Tier 2: undetected_chromedriver headless
        results = self._search_selenium(role, location, max_results)
        if results:
            return results

        console.print(
            "[yellow]⚠ LinkedIn scraping unavailable.[/yellow] "
            "Add LINKEDIN_LI_AT_COOKIE to .env for authenticated access, "
            "or use --sources seek to skip LinkedIn."
        )
        return []

    def _search_public(self, role: str, location: str, max_results: int) -> list[dict]:
        url = PUBLIC_SEARCH.format(
            role=role.replace(" ", "%20"),
            location=location.replace(" ", "%20"),
        )
        soup = self._fetch_page(url)
        if not soup:
            return []

        # Try JSON-LD JobPosting schema first
        jobs = self._parse_jsonld(soup)
        if jobs:
            return jobs[:max_results]

        # Fallback: parse job cards from HTML
        jobs = self._parse_cards(soup)
        return jobs[:max_results]

    def _search_selenium(self, role: str, location: str, max_results: int) -> list[dict]:
        try:
            import undetected_chromedriver as uc
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support import expected_conditions as EC
            from selenium.webdriver.support.ui import WebDriverWait
        except ImportError:
            return []

        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-gpu")

        driver = None
        try:
            driver = uc.Chrome(options=options, version_main=None)

            if self._li_at:
                driver.get("https://www.linkedin.com")
                driver.add_cookie({"name": "li_at", "value": self._li_at, "domain": ".linkedin.com"})

            url = PUBLIC_SEARCH.format(
                role=role.replace(" ", "%20"),
                location=location.replace(" ", "%20"),
            )
            driver.get(url)
            time.sleep(random.uniform(3, 6))

            # Scroll to load more results
            for _ in range(3):
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(random.uniform(2, 4))

            soup = BeautifulSoup(driver.page_source, "lxml")
            jobs = self._parse_jsonld(soup) or self._parse_cards(soup)
            return jobs[:max_results]
        except Exception as e:
            console.print(f"[dim]LinkedIn Selenium tier failed: {e}[/dim]")
            return []
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

    def _parse_jsonld(self, soup: BeautifulSoup) -> list[dict]:
        jobs = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, list):
                    items = data
                else:
                    items = [data] if data.get("@type") == "JobPosting" else data.get("@graph", [])
                for item in items:
                    if item.get("@type") == "JobPosting":
                        jobs.append({
                            "title": item.get("title", ""),
                            "company": item.get("hiringOrganization", {}).get("name", "Unknown"),
                            "url": item.get("url") or item.get("sameAs", ""),
                            "location": item.get("jobLocation", {}).get("address", {}).get("addressLocality", ""),
                            "salary_range": None,
                            "description": BeautifulSoup(item.get("description", ""), "lxml").get_text(strip=True),
                            "source": self.SOURCE,
                        })
            except Exception:
                continue
        return jobs

    def _parse_cards(self, soup: BeautifulSoup) -> list[dict]:
        jobs = []
        cards = (
            soup.select("div.base-card")
            or soup.select("li.jobs-search-results__list-item")
            or soup.select("[data-entity-urn]")
        )
        for card in cards:
            try:
                title_el = card.select_one("h3") or card.select_one(".base-search-card__title")
                company_el = card.select_one("h4") or card.select_one(".base-search-card__subtitle")
                link_el = card.select_one("a[href*='/jobs/']")
                if not (title_el and link_el):
                    continue
                href = link_el.get("href", "")
                url = href.split("?")[0] if href else ""
                jobs.append({
                    "title": title_el.get_text(strip=True),
                    "company": company_el.get_text(strip=True) if company_el else "Unknown",
                    "url": url,
                    "location": "",
                    "salary_range": None,
                    "description": self._fetch_job_description(url),
                    "source": self.SOURCE,
                })
                time.sleep(random.uniform(3, 6))
            except Exception:
                continue
        return jobs

    def _fetch_job_description(self, job_url: str) -> str:
        if not job_url:
            return ""
        soup = self._fetch_page(job_url)
        if not soup:
            return ""
        el = soup.select_one("div.show-more-less-html__markup") or soup.select_one(".description__text")
        return el.get_text(separator="\n", strip=True) if el else ""
