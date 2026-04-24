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
        session.get.side_effect = _mock_get_responses()

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
        session.get.side_effect = _mock_get_responses()

        result = extract_all(bo_config, output_dir=output_dir, report_filter="RDST")

    data = json.loads((output_dir / "bo-extracted" / "bo_extracted.json").read_text())
    assert data["extracted_count"] == 1
    assert data["reports"][0]["name"] == "RDST Summary"
