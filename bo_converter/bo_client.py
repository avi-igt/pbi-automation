"""SAP BusinessObjects REST API client.

Handles authentication, document enumeration, and per-report metadata
extraction via the BO RESTful Web Service (biprws).
"""

import logging
import time
from urllib.parse import unquote

import requests

from bo_converter.config import BoConfig

log = logging.getLogger(__name__)

_PAGE_SIZE = 50


def _as_list(val):
    """Normalise BO API responses that return a single dict instead of a list."""
    if val is None:
        return []
    return val if isinstance(val, list) else [val]


class BoClient:

    def __init__(self, config: BoConfig):
        self._cfg = config
        self._session = requests.Session()
        self._session.headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json",
        })
        self._folder_cache: dict[str, str] = {}
        self._folder_path_cache: dict[str, str] = {}

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
        all_docs: list[dict] = []
        offset = 0
        while True:
            url = f"{self._cfg.host}/raylight/v1/documents?offset={offset}&limit={_PAGE_SIZE}"
            resp = self._session.get(url)
            resp.raise_for_status()
            data = resp.json()
            page = _as_list(data.get("documents", {}).get("document", []))
            page = [d for d in page if d.get("id")]
            if not page:
                break
            all_docs.extend(page)
            if len(page) < _PAGE_SIZE:
                break
            offset += _PAGE_SIZE
        log.info("Enumerated %d WebI documents", len(all_docs))
        return all_docs

    def extract_report(self, doc: dict) -> dict:
        doc_id = doc["id"]
        name = doc["name"]
        description = doc.get("description", "")
        folder_id = str(doc.get("folderId", ""))

        folder_path = self._resolve_folder_path(folder_id)
        folder_name = self._resolve_folder(folder_id)

        parameters = self._extract_parameters(doc_id)
        dataproviders = self._extract_dataproviders(doc_id)
        layout = self._extract_layout(doc_id, dataproviders)

        report = {
            "folder": folder_name,
            "folder_path": folder_path,
            "name": name,
            "report_format": "Paginated",
            "legacy_reports": f"{folder_path}\\{name}",
            "legacy_users": "",
            "summary": description,
            "sort": "N/A",
            "target_folder": folder_name,
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

    def resolve_folder(self, doc_or_id) -> str:
        folder_id = str(doc_or_id.get("folderId", "")) if isinstance(doc_or_id, dict) else str(doc_or_id)
        return self._resolve_folder(folder_id)

    def resolve_folder_path(self, doc_or_id) -> str:
        folder_id = str(doc_or_id.get("folderId", "")) if isinstance(doc_or_id, dict) else str(doc_or_id)
        return self._resolve_folder_path(folder_id)

    def _resolve_folder(self, folder_id: str) -> str:
        if not folder_id:
            return ""
        if folder_id in self._folder_cache:
            return self._folder_cache[folder_id]
        data = self._fetch_folder(folder_id)
        if data is None:
            self._folder_cache[folder_id] = folder_id
            return folder_id
        name = data.get("name", folder_id)
        self._folder_cache[folder_id] = name
        return name

    def _resolve_folder_path(self, folder_id: str) -> str:
        if not folder_id:
            return ""
        if folder_id in self._folder_path_cache:
            return self._folder_path_cache[folder_id]
        data = self._fetch_folder(folder_id)
        if data is None:
            self._folder_path_cache[folder_id] = folder_id
            return folder_id
        name = data.get("name", folder_id)
        parent_uri = data.get("up", {}).get("__deferred", {}).get("uri", "")
        if parent_uri:
            parent_id = unquote(parent_uri.rstrip("/").split("/")[-1])
            if parent_id and parent_id != folder_id and parent_id not in ("Root Folder",):
                parent_path = self._resolve_folder_path(parent_id)
                path = f"{parent_path}/{name}"
            else:
                path = name
        else:
            path = name
        self._folder_path_cache[folder_id] = path
        self._folder_cache[folder_id] = name
        return path

    def _fetch_folder(self, folder_id: str) -> dict | None:
        url = f"{self._cfg.host}/infostore/{folder_id}"
        resp = self._session.get(url)
        if resp.status_code != 200:
            log.warning("Failed to resolve folder %s: %s", folder_id, resp.status_code)
            return None
        return resp.json()

    def _extract_parameters(self, doc_id) -> list[dict]:
        url = f"{self._cfg.host}/raylight/v1/documents/{doc_id}/parameters"
        resp = self._session.get(url)
        if resp.status_code != 200:
            log.warning("Failed to get parameters for doc %s: %s", doc_id, resp.status_code)
            return []
        data = resp.json()
        raw_params = _as_list(data.get("parameters", {}).get("parameter", []))
        params = []
        for p in raw_params:
            optional = p.get("@optional", "true")
            required = optional == "false"
            cardinality = (
                p.get("answer", {}).get("info", {}).get("@cardinality", "Single")
            )
            params.append({
                "label": p.get("name", ""),
                "required": required,
                "select": cardinality,
                "notes": "",
            })
        return params

    def _extract_dataproviders(self, doc_id) -> list[dict]:
        url = f"{self._cfg.host}/raylight/v1/documents/{doc_id}/dataproviders"
        resp = self._session.get(url)
        if resp.status_code != 200:
            log.warning("Failed to get dataproviders for doc %s: %s", doc_id, resp.status_code)
            return []
        data = resp.json()
        raw_dp = _as_list(data.get("dataproviders", {}).get("dataprovider", []))
        providers = []
        for dp in raw_dp:
            dp_id = dp.get("id", "")
            detail = self._get_dataprovider_detail(doc_id, dp_id)
            qp = self._get_queryplan(doc_id, dp_id)
            providers.append({
                "id": dp_id,
                "name": dp.get("name", ""),
                "dataSourceName": detail.get("dataSourceName", ""),
                "dataSourceType": dp.get("dataSourceType", ""),
                "columns": detail.get("columns", []),
                "sql": qp["sql"],
                "custom_sql": qp["custom"],
            })
        return providers

    def _get_dataprovider_detail(self, doc_id, dp_id: str) -> dict:
        url = f"{self._cfg.host}/raylight/v1/documents/{doc_id}/dataproviders/{dp_id}"
        resp = self._session.get(url)
        if resp.status_code != 200:
            return {}
        data = resp.json()
        dp = data.get("dataprovider", {})
        ds_name = dp.get("dataSourceName", "")
        exprs = _as_list(dp.get("dictionary", {}).get("expression", []))
        columns = [
            {
                "name": e.get("name", ""),
                "dataType": e.get("@dataType", ""),
                "qualification": e.get("@qualification", ""),
            }
            for e in exprs
        ]
        return {"dataSourceName": ds_name, "columns": columns}

    def _get_queryplan(self, doc_id, dp_id: str) -> dict:
        url = f"{self._cfg.host}/raylight/v1/documents/{doc_id}/dataproviders/{dp_id}/queryplan"
        resp = self._session.get(url)
        if resp.status_code != 200:
            return {"sql": "", "custom": False}
        data = resp.json()
        qp = data.get("queryplan", {})
        custom = qp.get("@custom", "false") == "true"
        stmt = qp.get("statement", {})
        if isinstance(stmt, dict):
            sql = stmt.get("$", "")
        elif isinstance(stmt, list):
            sql = "\n\n".join(s.get("$", "") for s in stmt if s.get("$"))
        else:
            sql = ""
        return {"sql": sql, "custom": custom}

    def _extract_layout(self, doc_id, dataproviders: list[dict]) -> dict:
        layout = {}
        for dp in dataproviders:
            dp_name = dp.get("name", "main")
            columns = [c["name"] for c in dp.get("columns", []) if c.get("name")]
            key = dp_name if dp_name else "main"
            if key in layout:
                key = f"{key} (continued)"
            layout[key] = {"columns": columns, "raw": ""}

        if not layout:
            layout["main"] = {"columns": [], "raw": ""}
        return layout
