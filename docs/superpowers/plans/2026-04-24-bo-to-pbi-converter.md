# BO-to-PBI Converter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a `bo_converter/` module in `pbi-automation` that extracts SAP BusinessObjects WebI report metadata via the BO REST API and generates `.md` spec files compatible with the existing Path B workflow (`spec_to_rdl.py`).

**Architecture:** Two-phase pipeline — Phase 1 calls the BO REST API to enumerate and extract all WebI reports into an intermediate `bo_extracted.json` (same schema as `frd_parsed.json`). Phase 2 normalises that JSON and delegates to `spec_generator.generate_md()` to produce `.md` spec files. Entry point is `convert_bo_reports.py` at the repo root.

**Tech Stack:** Python 3.12, `requests` (HTTP client), existing `report_generator.config` and `report_generator.spec_generator` modules, `pytest` for testing.

---

## File Structure

```
pbi-automation/
├── convert_bo_reports.py                    # CREATE — CLI entry point
├── requirements.txt                         # MODIFY — add requests
├── pbi.properties                           # MODIFY — add [bo] section
├── bo_converter/
│   ├── __init__.py                          # CREATE
│   ├── config.py                            # CREATE — reads [bo] from pbi.properties
│   ├── bo_client.py                         # CREATE — REST API session management
│   ├── bo_extractor.py                      # CREATE — orchestrates Phase 1
│   └── bo_spec_generator.py                 # CREATE — Phase 2, delegates to spec_generator
└── tests/
    └── bo_converter/
        ├── __init__.py                      # CREATE
        ├── conftest.py                      # CREATE — shared fixtures
        ├── test_config.py                   # CREATE
        ├── test_bo_client.py                # CREATE
        ├── test_bo_extractor.py             # CREATE
        └── test_bo_spec_generator.py        # CREATE
```

---

### Task 1: Project Scaffolding

**Files:**
- Modify: `requirements.txt`
- Modify: `pbi.properties`
- Create: `bo_converter/__init__.py`
- Create: `tests/__init__.py`
- Create: `tests/bo_converter/__init__.py`

- [ ] **Step 1: Add `requests` to requirements.txt**

Open `requirements.txt` and append:

```
requests>=2.28.0
```

- [ ] **Step 2: Add `[bo]` section to `pbi.properties`**

Append to the end of `pbi.properties`:

```ini
[bo]
host = http://10.17.56.65:8080/biprws
# Password via BO_PASSWORD env var — never stored here
```

- [ ] **Step 3: Create empty `__init__.py` files**

```bash
mkdir -p bo_converter tests/bo_converter
touch bo_converter/__init__.py tests/__init__.py tests/bo_converter/__init__.py
```

- [ ] **Step 4: Install dependencies**

```bash
pip3 install requests>=2.28.0 pytest
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt pbi.properties bo_converter/__init__.py tests/__init__.py tests/bo_converter/__init__.py
git commit -m "feat(bo_converter): scaffold project structure and dependencies"
```

---

### Task 2: bo_converter/config.py

**Files:**
- Create: `bo_converter/config.py`
- Create: `tests/bo_converter/test_config.py`

- [ ] **Step 1: Write the failing test**

Create `tests/bo_converter/test_config.py`:

```python
import os
import pytest
from bo_converter.config import BoConfig


def test_reads_bo_host(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text(
        "[bo]\n"
        "host = http://10.17.56.65:8080/biprws\n"
        "\n"
        "[datasource_keywords]\n"
        "default_datasource = semantic_model\n"
        "snowflake = rdst, tmir\n"
        "\n"
        "[model_keywords]\n"
        "MO_Sales = sales\n"
    )
    cfg = BoConfig(props)
    assert cfg.host == "http://10.17.56.65:8080/biprws"


def test_password_from_env(tmp_path, monkeypatch):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    monkeypatch.setenv("BO_PASSWORD", "secret123")
    cfg = BoConfig(props)
    assert cfg.password == "secret123"


def test_password_missing_raises(tmp_path, monkeypatch):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    monkeypatch.delenv("BO_PASSWORD", raising=False)
    cfg = BoConfig(props)
    with pytest.raises(ValueError, match="BO_PASSWORD"):
        _ = cfg.password


def test_username_from_config(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\nusername = admin\n")
    cfg = BoConfig(props)
    assert cfg.username == "admin"


def test_username_default(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    cfg = BoConfig(props)
    assert cfg.username == "Administrator"


def test_auth_type_default(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    cfg = BoConfig(props)
    assert cfg.auth_type == "secEnterprise"


def test_request_delay_default(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    cfg = BoConfig(props)
    assert cfg.request_delay == 0.2
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /mnt/c/Users/asingh/git/pbi-automation
python3 -m pytest tests/bo_converter/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bo_converter.config'`

- [ ] **Step 3: Write the implementation**

Create `bo_converter/config.py`:

```python
"""Configuration for the BO-to-PBI converter.

Reads the [bo] section from pbi.properties and exposes BO REST API
connection settings. Wraps report_generator.config for shared keyword
inference (infer_datasource, infer_semantic_model).
"""

import os
from configparser import ConfigParser
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent


class BoConfig:

    def __init__(self, properties_path: Path | None = None):
        self._cp = ConfigParser()
        path = properties_path or (_REPO_ROOT / "pbi.properties")
        self._cp.read(path)

        bo = dict(self._cp.items("bo")) if self._cp.has_section("bo") else {}
        self.host = bo.get("host", "").rstrip("/")
        self.username = bo.get("username", "Administrator")
        self.auth_type = bo.get("auth_type", "secEnterprise")
        self.request_delay = float(bo.get("request_delay", "0.2"))

    @property
    def password(self) -> str:
        pw = os.environ.get("BO_PASSWORD")
        if not pw:
            raise ValueError(
                "BO_PASSWORD environment variable is not set. "
                "Export it before running: export BO_PASSWORD=..."
            )
        return pw


cfg = BoConfig()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
python3 -m pytest tests/bo_converter/test_config.py -v
```

Expected: all 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bo_converter/config.py tests/bo_converter/test_config.py
git commit -m "feat(bo_converter): add config module for BO REST API settings"
```

---

### Task 3: bo_converter/bo_client.py

**Files:**
- Create: `bo_converter/bo_client.py`
- Create: `tests/bo_converter/conftest.py`
- Create: `tests/bo_converter/test_bo_client.py`

- [ ] **Step 1: Write test fixtures**

Create `tests/bo_converter/conftest.py`:

```python
import pytest
from bo_converter.config import BoConfig


@pytest.fixture
def bo_config(tmp_path, monkeypatch):
    props = tmp_path / "pbi.properties"
    props.write_text(
        "[bo]\n"
        "host = http://localhost:8080/biprws\n"
        "username = admin\n"
        "\n"
        "[datasource_keywords]\n"
        "default_datasource = semantic_model\n"
        "snowflake = rdst, tmir\n"
        "db2 = claims, payments\n"
        "\n"
        "[model_keywords]\n"
        "MO_Sales = sales\n"
    )
    monkeypatch.setenv("BO_PASSWORD", "testpass")
    return BoConfig(props)


LOGON_RESPONSE = {
    "logonToken": "COMMANDCOM-LCM:6400@{3&2=5291,U3&p=40674.9}",
}

INFOSTORE_PAGE1 = {
    "entries": {
        "entry": [
            {
                "SI_ID": 100,
                "SI_NAME": "Daily Sales Report",
                "SI_DESCRIPTION": "Shows daily sales by retailer",
                "SI_PATH": "Public Folders/Sales Reports/Daily Sales Report",
                "SI_KIND": "Webi",
                "SI_PARENT_FOLDER": 50,
            },
            {
                "SI_ID": 101,
                "SI_NAME": "RDST Summary",
                "SI_DESCRIPTION": "Snowflake RDST data",
                "SI_PATH": "Public Folders/Data Reports/RDST Summary",
                "SI_KIND": "Webi",
                "SI_PARENT_FOLDER": 51,
            },
        ]
    }
}

DOCUMENT_PARAMETERS = {
    "parameters": {
        "parameter": [
            {
                "id": 0,
                "name": "Enter Start Date:",
                "type": "DateTime",
                "mandatory": True,
                "multiValue": False,
            },
            {
                "id": 1,
                "name": "Enter End Date:",
                "type": "DateTime",
                "mandatory": True,
                "multiValue": False,
            },
            {
                "id": 2,
                "name": "Select Region:",
                "type": "String",
                "mandatory": False,
                "multiValue": True,
            },
        ]
    }
}

DOCUMENT_DATAPROVIDERS = {
    "dataproviders": {
        "dataprovider": [
            {
                "id": "DP0",
                "name": "Query 1",
                "dataSourceName": "Sales Universe",
                "dataSourceType": "unx",
            }
        ]
    }
}

DOCUMENT_REPORTS = {
    "reports": {
        "report": [
            {"id": 1, "name": "Report 1"},
        ]
    }
}

DOCUMENT_ELEMENTS = {
    "reportElements": {
        "reportElement": [
            {
                "id": "table1",
                "type": "Table",
                "name": "Block 1",
                "headers": {
                    "header": [
                        {"name": "Retailer No."},
                        {"name": "Retailer Name"},
                        {"name": "City"},
                        {"name": "Sales Amount"},
                    ]
                },
            }
        ]
    }
}
```

- [ ] **Step 2: Write failing tests for auth and enumerate**

Create `tests/bo_converter/test_bo_client.py`:

```python
from unittest.mock import MagicMock, patch, call
import pytest

from bo_converter.bo_client import BoClient
from tests.bo_converter.conftest import (
    LOGON_RESPONSE,
    INFOSTORE_PAGE1,
    DOCUMENT_PARAMETERS,
    DOCUMENT_DATAPROVIDERS,
    DOCUMENT_REPORTS,
    DOCUMENT_ELEMENTS,
)


class TestAuth:
    def test_logon_sets_token(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            session = MockSession.return_value
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = LOGON_RESPONSE
            session.post.return_value = resp

            client = BoClient(bo_config)
            client.logon()

            session.post.assert_called_once()
            assert "X-SAP-LogonToken" in session.headers

    def test_logoff_deletes_token(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            session = MockSession.return_value
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = LOGON_RESPONSE
            session.post.return_value = resp
            session.delete.return_value = MagicMock(status_code=200)

            client = BoClient(bo_config)
            client.logon()
            client.logoff()

            session.delete.assert_called_once()

    def test_context_manager(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            session = MockSession.return_value
            resp = MagicMock()
            resp.status_code = 200
            resp.json.return_value = LOGON_RESPONSE
            session.post.return_value = resp
            session.delete.return_value = MagicMock(status_code=200)

            with BoClient(bo_config) as client:
                assert client is not None

            session.delete.assert_called_once()


class TestEnumerate:
    def test_enumerate_returns_documents(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            session = MockSession.return_value
            resp_logon = MagicMock(status_code=200)
            resp_logon.json.return_value = LOGON_RESPONSE

            resp_info = MagicMock(status_code=200)
            resp_info.json.return_value = INFOSTORE_PAGE1

            session.post.return_value = resp_logon
            session.get.return_value = resp_info

            with BoClient(bo_config) as client:
                docs = client.enumerate_webi_documents()

            assert len(docs) == 2
            assert docs[0]["SI_NAME"] == "Daily Sales Report"
            assert docs[1]["SI_NAME"] == "RDST Summary"


class TestExtractReport:
    def _setup_client(self, MockSession):
        session = MockSession.return_value
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon

        resp_params = MagicMock(status_code=200)
        resp_params.json.return_value = DOCUMENT_PARAMETERS

        resp_dp = MagicMock(status_code=200)
        resp_dp.json.return_value = DOCUMENT_DATAPROVIDERS

        resp_reports = MagicMock(status_code=200)
        resp_reports.json.return_value = DOCUMENT_REPORTS

        resp_elements = MagicMock(status_code=200)
        resp_elements.json.return_value = DOCUMENT_ELEMENTS

        session.get.side_effect = [resp_params, resp_dp, resp_reports, resp_elements]
        return session

    def test_extract_parameters(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            self._setup_client(MockSession)

            doc = {"SI_ID": 100, "SI_NAME": "Test Report", "SI_DESCRIPTION": "desc", "SI_PATH": "Public Folders/Test"}
            with BoClient(bo_config) as client:
                report = client.extract_report(doc)

            assert len(report["parameters"]) == 3
            assert report["parameters"][0]["label"] == "Enter Start Date:"
            assert report["parameters"][0]["required"] is True
            assert report["parameters"][0]["select"] == "Single"
            assert report["parameters"][2]["select"] == "Multiple"

    def test_extract_layout_columns(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            self._setup_client(MockSession)

            doc = {"SI_ID": 100, "SI_NAME": "Test Report", "SI_DESCRIPTION": "desc", "SI_PATH": "Public Folders/Test"}
            with BoClient(bo_config) as client:
                report = client.extract_report(doc)

            assert "main" in report["layout"]
            assert report["layout"]["main"]["columns"] == [
                "Retailer No.", "Retailer Name", "City", "Sales Amount"
            ]

    def test_extract_maps_folder_from_path(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            self._setup_client(MockSession)

            doc = {"SI_ID": 100, "SI_NAME": "Test", "SI_DESCRIPTION": "", "SI_PATH": "Public Folders/Sales Reports/Test"}
            with BoClient(bo_config) as client:
                report = client.extract_report(doc)

            assert report["folder"] == "Sales Reports"
            assert report["legacy_reports"] == "Public Folders\\Sales Reports\\Test"
            assert report["name"] == "Test"
            assert report["report_format"] == "Paginated"
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
python3 -m pytest tests/bo_converter/test_bo_client.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bo_converter.bo_client'`

- [ ] **Step 4: Write the implementation**

Create `bo_converter/bo_client.py`:

```python
"""SAP BusinessObjects REST API client.

Handles authentication, document enumeration, and per-report metadata
extraction via the BO RESTful Web Service (biprws).
"""

import logging
import time
from typing import Any

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
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
python3 -m pytest tests/bo_converter/test_bo_client.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 6: Commit**

```bash
git add bo_converter/bo_client.py tests/bo_converter/conftest.py tests/bo_converter/test_bo_client.py
git commit -m "feat(bo_converter): add BO REST API client with auth, enumerate, extract"
```

---

### Task 4: bo_converter/bo_extractor.py

**Files:**
- Create: `bo_converter/bo_extractor.py`
- Create: `tests/bo_converter/test_bo_extractor.py`

- [ ] **Step 1: Write the failing test**

Create `tests/bo_converter/test_bo_extractor.py`:

```python
import json
from unittest.mock import MagicMock, patch
import pytest

from bo_converter.bo_extractor import extract_all
from bo_converter.config import BoConfig
from tests.bo_converter.conftest import (
    LOGON_RESPONSE,
    INFOSTORE_PAGE1,
    DOCUMENT_PARAMETERS,
    DOCUMENT_DATAPROVIDERS,
    DOCUMENT_REPORTS,
    DOCUMENT_ELEMENTS,
)


def _mock_get_responses():
    """Return a list of mock responses for a two-document extraction."""
    def make_resp(data, status=200):
        r = MagicMock(status_code=status)
        r.json.return_value = data
        return r

    return [
        make_resp(INFOSTORE_PAGE1),        # enumerate
        make_resp(DOCUMENT_PARAMETERS),    # doc 100 params
        make_resp(DOCUMENT_DATAPROVIDERS), # doc 100 dataproviders
        make_resp(DOCUMENT_REPORTS),       # doc 100 reports
        make_resp(DOCUMENT_ELEMENTS),      # doc 100 elements
        make_resp(DOCUMENT_PARAMETERS),    # doc 101 params
        make_resp(DOCUMENT_DATAPROVIDERS), # doc 101 dataproviders
        make_resp(DOCUMENT_REPORTS),       # doc 101 reports
        make_resp(DOCUMENT_ELEMENTS),      # doc 101 elements
    ]


def test_extract_all_writes_json(bo_config, tmp_path):
    output_dir = tmp_path / "output"
    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon
        session.delete.return_value = MagicMock(status_code=200)
        session.get.side_effect = _mock_get_responses()

        result = extract_all(bo_config, output_dir=output_dir)

    json_path = output_dir / "bo-extracted" / "bo_extracted.json"
    assert json_path.exists()
    data = json.loads(json_path.read_text())
    assert data["total_reports"] == 2
    assert data["extracted_count"] == 2
    assert data["error_count"] == 0
    assert len(data["reports"]) == 2
    assert data["reports"][0]["name"] == "Daily Sales Report"


def test_extract_all_with_folder_filter(bo_config, tmp_path):
    output_dir = tmp_path / "output"
    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon
        session.delete.return_value = MagicMock(status_code=200)
        session.get.side_effect = _mock_get_responses()

        result = extract_all(bo_config, output_dir=output_dir, folder_filter="Sales")

    data = json.loads((output_dir / "bo-extracted" / "bo_extracted.json").read_text())
    assert data["extracted_count"] == 1
    assert data["reports"][0]["folder"] == "Sales Reports"


def test_extract_all_with_report_filter(bo_config, tmp_path):
    output_dir = tmp_path / "output"
    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon
        session.delete.return_value = MagicMock(status_code=200)
        session.get.side_effect = _mock_get_responses()

        result = extract_all(bo_config, output_dir=output_dir, report_filter="RDST")

    data = json.loads((output_dir / "bo-extracted" / "bo_extracted.json").read_text())
    assert data["extracted_count"] == 1
    assert data["reports"][0]["name"] == "RDST Summary"


def test_extract_all_records_errors(bo_config, tmp_path):
    output_dir = tmp_path / "output"
    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon
        session.delete.return_value = MagicMock(status_code=200)

        resp_enum = MagicMock(status_code=200)
        resp_enum.json.return_value = INFOSTORE_PAGE1
        resp_fail = MagicMock(status_code=403)
        resp_fail.json.side_effect = Exception("forbidden")
        resp_fail.raise_for_status.side_effect = Exception("403 Forbidden")

        # First doc fails extraction, second succeeds
        session.get.side_effect = [
            resp_enum,                          # enumerate
            resp_fail,                          # doc 100 params (fails)
            MagicMock(status_code=200, json=MagicMock(return_value=DOCUMENT_PARAMETERS)),
            MagicMock(status_code=200, json=MagicMock(return_value=DOCUMENT_DATAPROVIDERS)),
            MagicMock(status_code=200, json=MagicMock(return_value=DOCUMENT_REPORTS)),
            MagicMock(status_code=200, json=MagicMock(return_value=DOCUMENT_ELEMENTS)),
        ]

        result = extract_all(bo_config, output_dir=output_dir)

    data = json.loads((output_dir / "bo-extracted" / "bo_extracted.json").read_text())
    assert data["error_count"] >= 1
    assert len(data["errors"]) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/bo_converter/test_bo_extractor.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bo_converter.bo_extractor'`

- [ ] **Step 3: Write the implementation**

Create `bo_converter/bo_extractor.py`:

```python
"""Phase 1 orchestrator — enumerate BO documents and write bo_extracted.json."""

import json
import logging
from pathlib import Path

from bo_converter.bo_client import BoClient
from bo_converter.config import BoConfig

log = logging.getLogger(__name__)


def extract_all(
    config: BoConfig,
    output_dir: Path | None = None,
    folder_filter: str | None = None,
    report_filter: str | None = None,
) -> Path:
    output_dir = Path(output_dir or "output")
    out_path = output_dir / "bo-extracted"
    out_path.mkdir(parents=True, exist_ok=True)
    json_path = out_path / "bo_extracted.json"

    reports = []
    errors = []

    with BoClient(config) as client:
        docs = client.enumerate_webi_documents()

        if folder_filter:
            docs = [
                d for d in docs
                if folder_filter.lower() in d.get("SI_PATH", "").lower()
            ]

        if report_filter:
            docs = [
                d for d in docs
                if report_filter.lower() in d.get("SI_NAME", "").lower()
            ]

        total = len(docs)
        log.info("Extracting %d documents (after filters)", total)

        for i, doc in enumerate(docs, 1):
            doc_id = doc.get("SI_ID", "?")
            doc_name = doc.get("SI_NAME", "?")
            log.info("[%d/%d] %s (id=%s)", i, total, doc_name, doc_id)
            try:
                report = client.extract_report(doc)
                reports.append(report)
            except Exception as e:
                log.warning("Failed to extract %s (id=%s): %s", doc_name, doc_id, e)
                errors.append({
                    "id": str(doc_id),
                    "name": doc_name,
                    "reason": str(e),
                })

    result = {
        "source": config.host,
        "total_reports": total,
        "extracted_count": len(reports),
        "error_count": len(errors),
        "errors": errors,
        "reports": reports,
    }

    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    log.info("Wrote %s (%d reports, %d errors)", json_path, len(reports), len(errors))
    return json_path
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/bo_converter/test_bo_extractor.py -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bo_converter/bo_extractor.py tests/bo_converter/test_bo_extractor.py
git commit -m "feat(bo_converter): add Phase 1 extractor orchestrating BO API to JSON"
```

---

### Task 5: bo_converter/bo_spec_generator.py

**Files:**
- Create: `bo_converter/bo_spec_generator.py`
- Create: `tests/bo_converter/test_bo_spec_generator.py`

- [ ] **Step 1: Write the failing test**

Create `tests/bo_converter/test_bo_spec_generator.py`:

```python
import json
from pathlib import Path
import pytest

from bo_converter.bo_spec_generator import generate_specs_from_json


SAMPLE_EXTRACTED = {
    "source": "http://localhost:8080/biprws",
    "total_reports": 1,
    "extracted_count": 1,
    "error_count": 0,
    "errors": [],
    "reports": [
        {
            "folder": "Sales Reports",
            "name": "Daily Sales Report",
            "report_format": "Paginated",
            "legacy_reports": "Public Folders\\Sales Reports\\Daily Sales Report",
            "legacy_users": "",
            "summary": "Shows daily sales by retailer",
            "sort": "N/A",
            "target_folder": "Sales Reports",
            "notes": "",
            "datasource_type": "semantic_model",
            "parameters": [
                {"label": "Start Date", "required": True, "select": "Single", "notes": ""},
                {"label": "End Date", "required": True, "select": "Single", "notes": ""},
            ],
            "filters": [],
            "layout": {
                "main": {
                    "columns": ["Retailer No.", "Retailer Name", "City", "Sales Amount"],
                    "raw": "",
                }
            },
            "requirements": [],
            "_dataproviders": [
                {"name": "Query 1", "dataSourceName": "Sales Universe", "dataSourceType": "unx"}
            ],
        }
    ],
}


def test_generates_md_files(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)

    assert len(paths) == 1
    assert paths[0].exists()
    content = paths[0].read_text()
    assert "# RDL Report Spec:" in content
    assert "Daily Sales Report" in content


def test_spec_contains_parameters(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)
    content = paths[0].read_text()

    assert "Start Date" in content
    assert "End Date" in content


def test_spec_contains_layout_columns(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)
    content = paths[0].read_text()

    assert "Retailer No." in content
    assert "Sales Amount" in content


def test_spec_contains_legacy_path(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)
    content = paths[0].read_text()

    assert "Public Folders" in content


def test_filename_is_slugified(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)

    assert paths[0].name == "daily-sales-report.md"


def test_skips_reports_with_filter(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir, report_filter="NONEXISTENT")

    assert len(paths) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/bo_converter/test_bo_spec_generator.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'bo_converter.bo_spec_generator'`

- [ ] **Step 3: Write the implementation**

Create `bo_converter/bo_spec_generator.py`:

```python
"""Phase 2 — convert bo_extracted.json into .md spec files.

Normalises BO JSON into the shape that spec_generator.generate_md() expects,
then delegates rendering. This avoids duplicating any markdown formatting logic.
"""

import json
import logging
import re
from pathlib import Path

from report_generator.spec_generator import generate_md
from report_generator.config import cfg as rpt_cfg

log = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    return slug.strip("-")


def _normalise_summary(report: dict) -> dict:
    return {
        "title": report.get("name", ""),
        "legacy_path": report.get("legacy_reports", ""),
        "legacy_users": report.get("legacy_users", ""),
        "description": report.get("summary", ""),
        "format": report.get("report_format", "Paginated"),
        "sort": report.get("sort", "N/A"),
        "folder": report.get("target_folder", ""),
        "notes": report.get("notes", ""),
    }


def _normalise_params(report: dict) -> tuple[list[dict], str]:
    if report.get("filters"):
        return report["filters"], "Filters"
    return report.get("parameters", []), "Parameters"


def _normalise_layout(report: dict) -> list[dict]:
    raw_layout = report.get("layout", {})
    tabs = []
    for section_name, section_data in raw_layout.items():
        columns = section_data.get("columns", [])
        tabs.append({"tab": section_name, "columns": columns})
    return tabs if tabs else [{"tab": "main", "columns": []}]


def _normalise_requirements(report: dict) -> list[str]:
    reqs = report.get("requirements", [])
    return [r.get("text", r) if isinstance(r, dict) else str(r) for r in reqs]


def _infer_datasource(report: dict) -> str:
    ds = report.get("datasource_type", "")
    if ds:
        return ds
    report_for_inference = {
        "name": report.get("name", ""),
        "summary": report.get("summary", ""),
        "notes": report.get("notes", ""),
    }
    return rpt_cfg.infer_datasource(report_for_inference)


def _infer_semantic_model(report: dict) -> str:
    report_for_inference = {
        "name": report.get("name", ""),
        "summary": report.get("summary", ""),
    }
    return rpt_cfg.infer_semantic_model(report_for_inference)


def generate_specs_from_json(
    json_path: Path | str,
    output_dir: Path | str,
    report_filter: str | None = None,
) -> list[Path]:
    json_path = Path(json_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    data = json.loads(json_path.read_text(encoding="utf-8"))
    reports = data.get("reports", [])

    if report_filter:
        reports = [
            r for r in reports
            if report_filter.lower() in r.get("name", "").lower()
        ]

    generated = []
    for report in reports:
        name = report.get("name", "Untitled")
        summary = _normalise_summary(report)
        params, param_section = _normalise_params(report)
        layout = _normalise_layout(report)
        reqs = _normalise_requirements(report)
        ds_type = _infer_datasource(report)
        model = _infer_semantic_model(report) if ds_type == "semantic_model" else ""

        md = generate_md(
            report_name=name,
            summary=summary,
            params=params,
            layout=layout,
            reqs=reqs,
            gen_reqs={},
            param_section=param_section,
            datasource_type=ds_type,
            semantic_model=model,
        )

        filename = f"{_slugify(name)}.md"
        out_path = output_dir / filename
        out_path.write_text(md, encoding="utf-8")
        log.info("Wrote spec: %s", out_path)
        generated.append(out_path)

    log.info("Generated %d spec files in %s", len(generated), output_dir)
    return generated
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python3 -m pytest tests/bo_converter/test_bo_spec_generator.py -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add bo_converter/bo_spec_generator.py tests/bo_converter/test_bo_spec_generator.py
git commit -m "feat(bo_converter): add Phase 2 spec generator delegating to spec_generator.generate_md"
```

---

### Task 6: convert_bo_reports.py (CLI Entry Point)

**Files:**
- Create: `convert_bo_reports.py`

- [ ] **Step 1: Write the implementation**

Create `convert_bo_reports.py` at repo root:

```python
#!/usr/bin/env python3
"""BO-to-PBI Converter — extract SAP BusinessObjects WebI metadata and generate PBI specs.

Usage:
    python convert_bo_reports.py                        # full pipeline
    python convert_bo_reports.py --only extract         # Phase 1: BO API → JSON
    python convert_bo_reports.py --only specs           # Phase 2: JSON → .md specs
    python convert_bo_reports.py --folder "Sales"       # filter by BO folder
    python convert_bo_reports.py --report "Daily Sales" # filter by report name
"""

import argparse
import logging
import sys
import time
from pathlib import Path

_REPO_ROOT = Path(__file__).parent


def _banner():
    print()
    print("  BO-to-PBI Converter")
    print("  SAP BusinessObjects → Power BI Report Specs")
    print()


def _elapsed(start: float) -> str:
    s = time.time() - start
    return f"{s:.1f}s" if s < 60 else f"{int(s // 60)}m {int(s % 60)}s"


def main():
    parser = argparse.ArgumentParser(description="Convert BO WebI reports to PBI specs")
    parser.add_argument(
        "--only",
        choices=["extract", "specs"],
        help="Run a single phase (extract=Phase 1, specs=Phase 2)",
    )
    parser.add_argument("--folder", help="Filter by BO folder (substring, case-insensitive)")
    parser.add_argument("--report", help="Filter by report name (substring, case-insensitive)")
    parser.add_argument("-o", "--output", default="output", help="Base output directory")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)-8s %(message)s",
    )

    _banner()
    output_dir = Path(args.output)
    start = time.time()

    from bo_converter.config import BoConfig
    config = BoConfig()

    run_extract = args.only in (None, "extract")
    run_specs = args.only in (None, "specs")

    json_path = output_dir / "bo-extracted" / "bo_extracted.json"

    if run_extract:
        print(f"  Phase 1: Extracting from {config.host}")
        from bo_converter.bo_extractor import extract_all
        json_path = extract_all(
            config,
            output_dir=output_dir,
            folder_filter=args.folder,
            report_filter=args.report,
        )
        print(f"  Phase 1 complete → {json_path}  ({_elapsed(start)})")
        print()

    if run_specs:
        if not json_path.exists():
            print(f"  ERROR: {json_path} not found — run --only extract first")
            sys.exit(1)

        specs_dir = output_dir / "bo-specs"
        print(f"  Phase 2: Generating specs from {json_path}")
        from bo_converter.bo_spec_generator import generate_specs_from_json
        paths = generate_specs_from_json(
            json_path,
            specs_dir,
            report_filter=args.report,
        )
        print(f"  Phase 2 complete → {len(paths)} specs in {specs_dir}  ({_elapsed(start)})")
        print()

    print(f"  Done in {_elapsed(start)}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify CLI help**

```bash
cd /mnt/c/Users/asingh/git/pbi-automation
python3 convert_bo_reports.py --help
```

Expected: prints usage with `--only`, `--folder`, `--report`, `-o`, `-v` flags

- [ ] **Step 3: Commit**

```bash
git add convert_bo_reports.py
git commit -m "feat(bo_converter): add CLI entry point convert_bo_reports.py"
```

---

### Task 7: Integration Smoke Test

**Files:**
- Create: `tests/bo_converter/test_integration.py`

- [ ] **Step 1: Write end-to-end test with mocked HTTP**

Create `tests/bo_converter/test_integration.py`:

```python
"""End-to-end test: BO API (mocked) → JSON → .md specs."""

import json
from unittest.mock import MagicMock, patch
import pytest

from bo_converter.config import BoConfig
from bo_converter.bo_extractor import extract_all
from bo_converter.bo_spec_generator import generate_specs_from_json
from tests.bo_converter.conftest import (
    LOGON_RESPONSE,
    INFOSTORE_PAGE1,
    DOCUMENT_PARAMETERS,
    DOCUMENT_DATAPROVIDERS,
    DOCUMENT_REPORTS,
    DOCUMENT_ELEMENTS,
)


def _make_resp(data, status=200):
    r = MagicMock(status_code=status)
    r.json.return_value = data
    return r


def test_full_pipeline(bo_config, tmp_path):
    output_dir = tmp_path / "output"

    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        session.post.return_value = _make_resp(LOGON_RESPONSE)
        session.delete.return_value = MagicMock(status_code=200)
        session.get.side_effect = [
            _make_resp(INFOSTORE_PAGE1),       # enumerate
            _make_resp(DOCUMENT_PARAMETERS),   # doc 100
            _make_resp(DOCUMENT_DATAPROVIDERS),
            _make_resp(DOCUMENT_REPORTS),
            _make_resp(DOCUMENT_ELEMENTS),
            _make_resp(DOCUMENT_PARAMETERS),   # doc 101
            _make_resp(DOCUMENT_DATAPROVIDERS),
            _make_resp(DOCUMENT_REPORTS),
            _make_resp(DOCUMENT_ELEMENTS),
        ]

        # Phase 1
        json_path = extract_all(bo_config, output_dir=output_dir)

    # Verify JSON
    data = json.loads(json_path.read_text())
    assert data["extracted_count"] == 2

    # Phase 2
    specs_dir = output_dir / "bo-specs"
    paths = generate_specs_from_json(json_path, specs_dir)

    assert len(paths) == 2

    # Verify first spec has expected content
    content = paths[0].read_text()
    assert "# RDL Report Spec:" in content
    assert "Daily Sales Report" in content
    assert "Enter Start Date:" in content
    assert "Retailer No." in content
    assert "Public Folders" in content

    # Verify second spec exists
    content2 = paths[1].read_text()
    assert "RDST Summary" in content2
```

- [ ] **Step 2: Run full test suite**

```bash
python3 -m pytest tests/bo_converter/ -v
```

Expected: all tests PASS (config: 7, client: 6, extractor: 4, spec_generator: 6, integration: 1 = 24 total)

- [ ] **Step 3: Commit**

```bash
git add tests/bo_converter/test_integration.py
git commit -m "test(bo_converter): add end-to-end integration test with mocked BO API"
```

---

### Task 8: Documentation

**Files:**
- Modify: `README.md` (add bo_converter section)

- [ ] **Step 1: Add bo_converter section to README.md**

Find the section after model_generator documentation and add:

```markdown
## Tool 3 — bo_converter

Extracts SAP BusinessObjects WebI report metadata via the BO REST API and generates
Power BI `.md` spec files for the existing Path B workflow.

### Configuration

Add a `[bo]` section to `pbi.properties`:

```ini
[bo]
host = http://10.17.56.65:8080/biprws
username = your.name@ourlotto.com
```

Set `BO_PASSWORD` as an environment variable (never in config).

### Running

```bash
export BO_PASSWORD=...

# Full pipeline (extract + specs)
python convert_bo_reports.py

# Phase 1 only — hit BO API, write bo_extracted.json
python convert_bo_reports.py --only extract

# Phase 2 only — generate specs from existing JSON
python convert_bo_reports.py --only specs

# Filter by BO folder or report name
python convert_bo_reports.py --folder "Sales Reports"
python convert_bo_reports.py --report "Daily Sales"
```

### Workflow

1. `python convert_bo_reports.py --only extract` — Pull metadata from BO
2. Inspect `output/bo-extracted/bo_extracted.json` — Sanity check
3. `python convert_bo_reports.py --only specs` — Generate .md spec files
4. Edit `output/bo-specs/*.md` — Human review and fill in SQL, confirm models
5. `python report_generator/spec_to_rdl.py output/bo-specs/` — Generate .rdl files via Path B
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add bo_converter usage to README"
```

---

### Task 9: Adapt to Live BO API Responses

> **Note:** This task runs after initial deployment against the real BO server. The mocked response shapes above are based on the SAP BO 4.x REST API documentation. The actual response JSON keys and nesting may differ slightly depending on BO version. This task captures the expected tuning.

**Files:**
- Modify: `bo_converter/bo_client.py` (adjust response parsing as needed)
- Modify: `tests/bo_converter/conftest.py` (update fixtures to match real responses)

- [ ] **Step 1: Run Phase 1 against real BO server**

```bash
export BO_PASSWORD=...
python3 convert_bo_reports.py --only extract --report "Daily Sales" -v
```

- [ ] **Step 2: Inspect the raw HTTP responses**

If extraction fails, add temporary debug logging to `bo_client.py`:

```python
log.debug("Raw response: %s", resp.text[:2000])
```

- [ ] **Step 3: Adjust response parsing in bo_client.py**

Common differences to watch for:
- `entries.entry` may be a single dict instead of a list when only one result
- Parameter field names may use camelCase (`multiValue`) or snake_case (`multi_value`)
- Element headers may nest differently (`columns` vs `headers.header`)
- Some endpoints may return XML despite `Accept: application/json` — add XML fallback parsing if needed

- [ ] **Step 4: Update test fixtures to match real response shapes**

- [ ] **Step 5: Re-run full test suite and commit**

```bash
python3 -m pytest tests/bo_converter/ -v
git add -A && git commit -m "fix(bo_converter): adapt response parsing to live BO API"
```
