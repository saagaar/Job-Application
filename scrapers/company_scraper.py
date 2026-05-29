from __future__ import annotations

import json
import re
from typing import Optional

from bs4 import BeautifulSoup

from scrapers.base_scraper import BaseScraper


class CompanyScraper(BaseScraper):
    SOURCE = "company_page"

    def scrape_url(self, careers_url: str, company_name: str) -> list[dict]:
        soup = self._fetch_page(careers_url)
        if not soup:
            return []

        ats = self._detect_ats(soup, careers_url)
        if ats == "greenhouse":
            handle = self._extract_greenhouse_handle(careers_url)
            if handle:
                return self._scrape_greenhouse(handle, company_name)
        elif ats == "lever":
            handle = self._extract_lever_handle(careers_url)
            if handle:
                return self._scrape_lever(handle, company_name)

        # Generic: JSON-LD fallback then link extraction
        jobs = self._parse_jsonld(soup, company_name)
        if jobs:
            return jobs
        return self._scrape_links(soup, careers_url, company_name)

    def _detect_ats(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        url_lower = url.lower()
        if "greenhouse.io" in url_lower or "boards.greenhouse" in url_lower:
            return "greenhouse"
        if "lever.co" in url_lower:
            return "lever"
        if "workday.com" in url_lower:
            return "workday"
        if "smartrecruiters.com" in url_lower:
            return "smartrecruiters"
        # Check page meta / scripts
        page_text = str(soup)[:5000]
        if "greenhouse" in page_text:
            return "greenhouse"
        if "lever.co" in page_text:
            return "lever"
        return None

    def _scrape_greenhouse(self, company_handle: str, company_name: str) -> list[dict]:
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{company_handle}/jobs?content=true"
        try:
            resp = self.session.get(api_url, timeout=15)
            if resp.status_code != 200:
                return []
            data = resp.json()
            jobs = []
            for item in data.get("jobs", []):
                jobs.append({
                    "title": item.get("title", ""),
                    "company": company_name,
                    "url": item.get("absolute_url", ""),
                    "location": item.get("location", {}).get("name", ""),
                    "salary_range": None,
                    "description": BeautifulSoup(item.get("content", ""), "lxml").get_text(strip=True),
                    "source": self.SOURCE,
                })
            return jobs
        except Exception:
            return []

    def _scrape_lever(self, company_handle: str, company_name: str) -> list[dict]:
        api_url = f"https://api.lever.co/v0/postings/{company_handle}?mode=json"
        try:
            resp = self.session.get(api_url, timeout=15)
            if resp.status_code != 200:
                return []
            jobs = []
            for item in resp.json():
                description = " ".join(
                    BeautifulSoup(block.get("content", ""), "lxml").get_text(strip=True)
                    for block in item.get("descriptionBody", {}).get("blocks", [])
                )
                jobs.append({
                    "title": item.get("text", ""),
                    "company": company_name,
                    "url": item.get("hostedUrl", ""),
                    "location": item.get("categories", {}).get("location", ""),
                    "salary_range": None,
                    "description": description,
                    "source": self.SOURCE,
                })
            return jobs
        except Exception:
            return []

    def _parse_jsonld(self, soup: BeautifulSoup, company_name: str) -> list[dict]:
        jobs = []
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else [data]
                for item in items:
                    if item.get("@type") == "JobPosting":
                        jobs.append({
                            "title": item.get("title", ""),
                            "company": company_name,
                            "url": item.get("url") or item.get("sameAs", ""),
                            "location": item.get("jobLocation", {}).get("address", {}).get("addressLocality", ""),
                            "salary_range": None,
                            "description": BeautifulSoup(item.get("description", ""), "lxml").get_text(strip=True),
                            "source": self.SOURCE,
                        })
            except Exception:
                continue
        return jobs

    def _scrape_links(self, soup: BeautifulSoup, base_url: str, company_name: str) -> list[dict]:
        job_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(strip=True).lower()
            if re.search(r"(job|position|role|career|opening|vacanc)", href + text, re.I):
                full = href if href.startswith("http") else base_url.rstrip("/") + "/" + href.lstrip("/")
                job_links.append((full, a.get_text(strip=True)))

        jobs = []
        for url, title in job_links[:20]:
            description = ""
            detail_soup = self._fetch_page(url)
            if detail_soup:
                main = detail_soup.select_one("main, article, .job-description, [class*='jobDetail']")
                description = main.get_text(separator="\n", strip=True) if main else ""
            if not description:
                continue
            jobs.append({
                "title": title,
                "company": company_name,
                "url": url,
                "location": "",
                "salary_range": None,
                "description": description,
                "source": self.SOURCE,
            })
        return jobs

    @staticmethod
    def _extract_greenhouse_handle(url: str) -> Optional[str]:
        match = re.search(r"boards\.greenhouse\.io/([^/?#]+)", url)
        return match.group(1) if match else None

    @staticmethod
    def _extract_lever_handle(url: str) -> Optional[str]:
        match = re.search(r"jobs\.lever\.co/([^/?#]+)", url)
        return match.group(1) if match else None
