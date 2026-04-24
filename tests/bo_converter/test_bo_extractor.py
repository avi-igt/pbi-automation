"""Phase 1 orchestrator tests — enumerate, filter, extract, write JSON."""

import json
from unittest.mock import MagicMock, patch
import pytest

from bo_converter.bo_extractor import extract_all
from bo_converter.config import BoConfig
from tests.bo_converter.conftest import (
    LOGON_RESPONSE,
    DOCUMENTS_LIST,
    FOLDER_50,
    FOLDER_51,
    DOCUMENT_PARAMETERS,
    DOCUMENT_DATAPROVIDERS,
    DATAPROVIDER_DETAIL,
)


def _make_resp(data, status=200):
    r = MagicMock(status_code=status)
    r.json.return_value = data
    return r


def _mock_get_responses():
    """Mock responses for extracting two documents.

    Sequence: enumerate → (folder + params + dp_list + dp_detail) × 2 docs.
    """
    return [
        _make_resp(DOCUMENTS_LIST),         # enumerate
        _make_resp(FOLDER_50),              # doc 100 folder resolve
        _make_resp(DOCUMENT_PARAMETERS),    # doc 100 params
        _make_resp(DOCUMENT_DATAPROVIDERS), # doc 100 dataproviders list
        _make_resp(DATAPROVIDER_DETAIL),    # doc 100 DP0 detail
        _make_resp(FOLDER_51),              # doc 101 folder resolve
        _make_resp(DOCUMENT_PARAMETERS),    # doc 101 params
        _make_resp(DOCUMENT_DATAPROVIDERS), # doc 101 dataproviders list
        _make_resp(DATAPROVIDER_DETAIL),    # doc 101 DP0 detail
    ]


def test_extract_all_writes_json(bo_config, tmp_path):
    output_dir = tmp_path / "output"
    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        session.headers = {}
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
        session.headers = {}
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon
        session.delete.return_value = MagicMock(status_code=200)
        # Folder filter calls resolve_folder for each doc during filtering,
        # then extract_report calls it again (but it's cached).
        # Sequence: enumerate → folder50 → folder51 (filter) → params + dp_list + dp_detail (doc 100 only)
        session.get.side_effect = [
            _make_resp(DOCUMENTS_LIST),         # enumerate
            _make_resp(FOLDER_50),              # resolve folder 50 for filter
            _make_resp(FOLDER_51),              # resolve folder 51 for filter
            _make_resp(DOCUMENT_PARAMETERS),    # doc 100 params (only Sales Reports match)
            _make_resp(DOCUMENT_DATAPROVIDERS), # doc 100 dataproviders list
            _make_resp(DATAPROVIDER_DETAIL),    # doc 100 DP0 detail
        ]

        result = extract_all(bo_config, output_dir=output_dir, folder_filter="Sales")

    data = json.loads((output_dir / "bo-extracted" / "bo_extracted.json").read_text())
    assert data["extracted_count"] == 1
    assert data["reports"][0]["folder"] == "Sales Reports"


def test_extract_all_with_report_filter(bo_config, tmp_path):
    output_dir = tmp_path / "output"
    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        session.headers = {}
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon
        session.delete.return_value = MagicMock(status_code=200)
        # Report filter uses doc["name"], no extra API calls.
        # Only doc 101 ("RDST Summary") matches.
        session.get.side_effect = [
            _make_resp(DOCUMENTS_LIST),         # enumerate
            _make_resp(FOLDER_51),              # doc 101 folder resolve
            _make_resp(DOCUMENT_PARAMETERS),    # doc 101 params
            _make_resp(DOCUMENT_DATAPROVIDERS), # doc 101 dataproviders list
            _make_resp(DATAPROVIDER_DETAIL),    # doc 101 DP0 detail
        ]

        result = extract_all(bo_config, output_dir=output_dir, report_filter="RDST")

    data = json.loads((output_dir / "bo-extracted" / "bo_extracted.json").read_text())
    assert data["extracted_count"] == 1
    assert data["reports"][0]["name"] == "RDST Summary"


def test_extract_all_records_errors(bo_config, tmp_path):
    output_dir = tmp_path / "output"
    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        session.headers = {}
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon
        session.delete.return_value = MagicMock(status_code=200)

        session.get.side_effect = [
            _make_resp(DOCUMENTS_LIST),  # enumerate
            # doc 100: folder resolve fails with exception
            MagicMock(status_code=200, json=MagicMock(side_effect=Exception("parse error"))),
            # doc 101: successful extraction
            _make_resp(FOLDER_51),              # folder resolve
            _make_resp(DOCUMENT_PARAMETERS),    # params
            _make_resp(DOCUMENT_DATAPROVIDERS), # dataproviders list
            _make_resp(DATAPROVIDER_DETAIL),    # DP0 detail
        ]

        result = extract_all(bo_config, output_dir=output_dir)

    data = json.loads((output_dir / "bo-extracted" / "bo_extracted.json").read_text())
    assert data["error_count"] >= 1
    assert len(data["errors"]) >= 1
    assert data["extracted_count"] >= 1
