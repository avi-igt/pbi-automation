"""SAP BusinessObjects REST API client.

Handles authentication, document enumeration, and per-report metadata
extraction via the BO RESTful Web Service (biprws).
"""

import logging
import time

import requests

from bo_converter.config import BoConfig

log = logging.getLogger(__name__)


class BoClient:

    def __init__(self, config: BoConfig):
        self._cfg = config
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })

    def __enter__(self):
        self.logon()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logoff()
        return False

    def logon(self):
        url = f"{self._cfg.host}/logon/long"
        payload = {
            "userName": self._cfg.username,
            "password": self._cfg.password,
            "auth": self._cfg.auth_type,
        }
        resp = self._session.post(url, json=payload)
        resp.raise_for_status()
        token = resp.json().get("logonToken")
        if not token:
            raise RuntimeError("Logon succeeded but no logonToken in response")
        self._session.headers["X-SAP-LogonToken"] = f'"{token}"'
        log.info("Logged on to %s as %s", self._cfg.host, self._cfg.username)

    def logoff(self):
        try:
            url = f"{self._cfg.host}/logon/long"
            self._session.delete(url)
            log.info("Logged off from %s", self._cfg.host)
        except Exception as e:
            log.warning("Logoff failed: %s", e)

    def enumerate_webi_documents(self) -> list[dict]:
        docs = []
        offset = 0
        limit = 50
        while True:
            query = (
                "SELECT SI_ID,SI_NAME,SI_DESCRIPTION,SI_PARENT_FOLDER,SI_PATH "
                "FROM CI_INFOOBJECTS WHERE SI_KIND='Webi'"
            )
            url = f"{self._cfg.host}/infostore"
            params = {"query": query, "offset": offset, "limit": limit}
            resp = self._session.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            entries = data.get("entries", {}).get("entry", [])
            if not entries:
                break
            docs.extend(entries)
            if len(entries) < limit:
                break
            offset += limit
        log.info("Enumerated %d WebI documents", len(docs))
        return docs

    def extract_report(self, doc: dict) -> dict:
        doc_id = doc["SI_ID"]
        name = doc["SI_NAME"]
        description = doc.get("SI_DESCRIPTION", "")
        si_path = doc.get("SI_PATH", "")

        path_parts = si_path.replace("\\", "/").split("/")
        folder = path_parts[-2] if len(path_parts) >= 2 else ""
        legacy_reports = si_path.replace("/", "\\")

        parameters = self._extract_parameters(doc_id)
        dataproviders = self._extract_dataproviders(doc_id)
        layout = self._extract_layout(doc_id)

        report = {
            "folder": folder,
            "name": name,
            "report_format": "Paginated",
            "legacy_reports": legacy_reports,
            "legacy_users": "",
            "summary": description,
            "sort": "N/A",
            "target_folder": folder,
            "notes": "",
            "datasource_type": "",
            "parameters": parameters,
            "filters": [],
            "layout": layout,
            "requirements": [],
            "_dataproviders": dataproviders,
        }

        time.sleep(self._cfg.request_delay)
        return report

    def _extract_parameters(self, doc_id: int) -> list[dict]:
        url = f"{self._cfg.host}/raylight/v1/documents/{doc_id}/parameters"
        resp = self._session.get(url)
        if resp.status_code != 200:
            log.warning("Failed to get parameters for doc %d: %s", doc_id, resp.status_code)
            return []
        data = resp.json()
        raw_params = data.get("parameters", {}).get("parameter", [])
        params = []
        for p in raw_params:
            params.append({
                "label": p.get("name", ""),
                "required": p.get("mandatory", False),
                "select": "Multiple" if p.get("multiValue", False) else "Single",
                "notes": "",
            })
        return params

    def _extract_dataproviders(self, doc_id: int) -> list[dict]:
        url = f"{self._cfg.host}/raylight/v1/documents/{doc_id}/dataproviders"
        resp = self._session.get(url)
        if resp.status_code != 200:
            log.warning("Failed to get dataproviders for doc %d: %s", doc_id, resp.status_code)
            return []
        data = resp.json()
        raw_dp = data.get("dataproviders", {}).get("dataprovider", [])
        return [
            {
                "name": dp.get("name", ""),
                "dataSourceName": dp.get("dataSourceName", ""),
                "dataSourceType": dp.get("dataSourceType", ""),
            }
            for dp in raw_dp
        ]

    def _extract_layout(self, doc_id: int) -> dict:
        reports_url = f"{self._cfg.host}/raylight/v1/documents/{doc_id}/reports"
        resp = self._session.get(reports_url)
        if resp.status_code != 200:
            log.warning("Failed to get reports for doc %d: %s", doc_id, resp.status_code)
            return {"main": {"columns": [], "raw": ""}}

        data = resp.json()
        raw_reports = data.get("reports", {}).get("report", [])
        layout = {}

        for report in raw_reports:
            rid = report["id"]
            tab_name = report.get("name", "main")
            elements_url = (
                f"{self._cfg.host}/raylight/v1/documents/{doc_id}/reports/{rid}/elements"
            )
            eresp = self._session.get(elements_url)
            if eresp.status_code != 200:
                continue
            edata = eresp.json()
            raw_elements = edata.get("reportElements", {}).get("reportElement", [])

            for elem in raw_elements:
                if elem.get("type") != "Table":
                    continue
                section_name = tab_name if tab_name != "Report 1" else "main"
                headers = elem.get("headers", {}).get("header", [])
                columns = [h.get("name", "") for h in headers if h.get("name")]
                key = section_name
                if key in layout:
                    key = f"{section_name} ({elem.get('name', 'continued')})"
                layout[key] = {"columns": columns, "raw": ""}

        if not layout:
            layout["main"] = {"columns": [], "raw": ""}
        return layout
