from __future__ import annotations

import re
import time
from typing import Optional

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper

BASE_URL = "https://www.seek.com.au"


class SeekScraper(BaseScraper):
    SOURCE = "seek"

    def search(self, role: str, location: str = "All-Australia", max_results: int = 50) -> list[dict]:
        results: list[dict] = []
        slug = self._slugify(role)
        loc_slug = self._slugify(location) if location.lower() != "australia" else "All-Australia"
        page = 1

        while len(results) < max_results:
            url = f"{BASE_URL}/{slug}-jobs/in-{loc_slug}?page={page}"
            soup = self._fetch_page(url)
            if not soup:
                break

            cards = soup.select('article[data-card-type="JobCard"]')
            if not cards:
                # Try alternate selector used on some pages
                cards = soup.select("article[data-automation='normalJob']")
            if not cards:
                break

            new_this_page = 0
            for card in cards:
                job = self._parse_card(card)
                if job:
                    description = self._fetch_description(job["url"])
                    job["description"] = description
                    results.append(job)
                    new_this_page += 1
                    if len(results) >= max_results:
                        break
                time.sleep(0.5)

            if new_this_page == 0:
                break
            page += 1
            time.sleep(1.0)

        return results

    def _parse_card(self, card: BeautifulSoup) -> Optional[dict]:
        try:
            title_el = card.select_one("a[data-automation='jobTitle']") or card.select_one("h3 a")
            if not title_el:
                return None
            title = title_el.get_text(strip=True)
            href = title_el.get("href", "")
            if not href:
                return None
            url = href if href.startswith("http") else BASE_URL + href

            company_el = card.select_one("a[data-automation='jobCompany']") or card.select_one("[data-automation='jobCompany']")
            company = company_el.get_text(strip=True) if company_el else "Unknown"

            location_el = card.select_one("[data-automation='jobCardLocation']") or card.select_one("span[data-automation='jobLocation']")
            location = location_el.get_text(strip=True) if location_el else ""

            salary_el = card.select_one("[data-automation='jobSalary']")
            salary = salary_el.get_text(strip=True) if salary_el else None

            return {
                "title": title,
                "company": company,
                "url": url,
                "location": location,
                "salary_range": salary,
                "source": self.SOURCE,
                "description": "",
            }
        except Exception:
            return None

    def _fetch_description(self, job_url: str) -> str:
        soup = self._fetch_page(job_url)
        if not soup:
            return ""
        # Primary selector
        el = soup.select_one("div[data-automation='jobAdDetails']")
        if el:
            return el.get_text(separator="\n", strip=True)
        # Fallback: largest article block
        for tag in soup.select("article, .job-detail, [class*='jobDetail']"):
            text = tag.get_text(separator="\n", strip=True)
            if len(text) > 200:
                return text
        return ""

    @staticmethod
    def _slugify(text: str) -> str:
        text = text.lower().strip()
        text = re.sub(r"[^a-z0-9\s-]", "", text)
        text = re.sub(r"[\s]+", "-", text)
        return text
