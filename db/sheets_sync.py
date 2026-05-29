from __future__ import annotations

from typing import Any

from db.models import Job

COLUMNS = [
    "id", "title", "company", "match_score", "status",
    "location", "salary_range", "date_found", "applied_date",
    "source", "url", "notes",
]
HEADERS = [
    "ID", "Job Title", "Company", "Match %", "Status",
    "Location", "Salary", "Date Found", "Applied",
    "Source", "URL", "Notes",
]


class SheetsSync:
    def __init__(self, spreadsheet_id: str, credentials_path: str):
        self._spreadsheet_id = spreadsheet_id
        self._credentials_path = credentials_path
        self._service = None

    def push_jobs(self, jobs: list[Job]) -> None:
        service = self._get_service()
        rows: list[list[Any]] = [HEADERS]
        for job in jobs:
            row = []
            for field in COLUMNS:
                val = getattr(job, field, None)
                if hasattr(val, "value"):
                    val = val.value
                if hasattr(val, "isoformat"):
                    val = val.strftime("%Y-%m-%d")
                    
                row.append(val if val is not None else "")
            rows.append(row)

        sheet_range = "Sheet1!A1"
        service.spreadsheets().values().clear(
            spreadsheetId=self._spreadsheet_id,
            range="Sheet1",
        ).execute()
        service.spreadsheets().values().update(
            spreadsheetId=self._spreadsheet_id,
            range=sheet_range,
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()

    def _get_service(self):
        if self._service:
            return self._service
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build

        creds = Credentials.from_service_account_file(
            self._credentials_path,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        self._service = build("sheets", "v4", credentials=creds)
        return self._service
