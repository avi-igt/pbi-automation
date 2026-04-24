"""End-to-end test: BO API (mocked) -> JSON -> .md specs."""

import json
from unittest.mock import MagicMock, patch
import pytest

from bo_converter.config import BoConfig
from bo_converter.bo_extractor import extract_all
from bo_converter.bo_spec_generator import generate_specs_from_json
from tests.bo_converter.conftest import (
    LOGON_RESPONSE,
    DOCUMENTS_LIST,
    ROOT_FOLDER,
    FOLDER_50,
    FOLDER_51,
    DOCUMENT_PARAMETERS,
    DOCUMENT_DATAPROVIDERS,
    DATAPROVIDER_DETAIL,
    DATAPROVIDER_QUERYPLAN,
)


def _make_resp(data, status=200):
    r = MagicMock(status_code=status)
    r.json.return_value = data
    return r


def _mock_get_responses():
    """Mock responses for two-document extraction.

    Sequence: enumerate -> (folder + params + dp_list + dp_detail) x 2 docs.
    """
    return [
        _make_resp(DOCUMENTS_LIST),         # enumerate
        _make_resp(FOLDER_50),              # doc 100 folder path: folder 50
        _make_resp(ROOT_FOLDER),            # doc 100 folder path: parent (root)
        _make_resp(DOCUMENT_PARAMETERS),    # doc 100 params
        _make_resp(DOCUMENT_DATAPROVIDERS), # doc 100 dataproviders list
        _make_resp(DATAPROVIDER_DETAIL),    # doc 100 DP0 detail
        _make_resp(DATAPROVIDER_QUERYPLAN), # doc 100 DP0 queryplan
        _make_resp(FOLDER_51),              # doc 101 folder path: folder 51 (root cached)
        _make_resp(DOCUMENT_PARAMETERS),    # doc 101 params
        _make_resp(DOCUMENT_DATAPROVIDERS), # doc 101 dataproviders list
        _make_resp(DATAPROVIDER_DETAIL),    # doc 101 DP0 detail
        _make_resp(DATAPROVIDER_QUERYPLAN), # doc 101 DP0 queryplan
    ]


def test_full_pipeline(bo_config, tmp_path):
    output_dir = tmp_path / "output"

    with patch("bo_converter.bo_client.requests.Session") as MockSession:
        session = MockSession.return_value
        session.headers = {}
        session.post.return_value = _make_resp(LOGON_RESPONSE)
        session.delete.return_value = MagicMock(status_code=200)
        session.get.side_effect = _mock_get_responses()

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
    assert "Sales Reports" in content

    # Verify second spec exists
    content2 = paths[1].read_text()
    assert "RDST Summary" in content2
