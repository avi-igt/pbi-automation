from unittest.mock import MagicMock, patch
import pytest

from bo_converter.bo_client import BoClient
from tests.bo_converter.conftest import (
    LOGON_RESPONSE,
    DOCUMENTS_LIST,
    DOCUMENT_PARAMETERS,
    DOCUMENT_DATAPROVIDERS,
    DATAPROVIDER_DETAIL,
    DATAPROVIDER_QUERYPLAN,
    FOLDER_50,
)


def _make_resp(data, status=200):
    r = MagicMock(status_code=status)
    r.json.return_value = data
    return r


class TestAuth:
    def test_logon_sets_token(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            session = MockSession.return_value
            session.headers = {}
            resp = MagicMock(status_code=200)
            resp.json.return_value = LOGON_RESPONSE
            session.post.return_value = resp

            client = BoClient(bo_config)
            client.logon()

            session.post.assert_called_once()
            assert "X-SAP-LogonToken" in session.headers

    def test_logoff_deletes_token(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            session = MockSession.return_value
            session.headers = {}
            resp = MagicMock(status_code=200)
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
            session.headers = {}
            resp = MagicMock(status_code=200)
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
            session.headers = {}
            resp_logon = MagicMock(status_code=200)
            resp_logon.json.return_value = LOGON_RESPONSE
            resp_docs = MagicMock(status_code=200)
            resp_docs.json.return_value = DOCUMENTS_LIST

            session.post.return_value = resp_logon
            session.get.return_value = resp_docs

            with BoClient(bo_config) as client:
                docs = client.enumerate_webi_documents()

            assert len(docs) == 2
            assert docs[0]["name"] == "Daily Sales Report"
            assert docs[1]["name"] == "RDST Summary"


class TestExtractReport:
    def _setup_client(self, MockSession):
        session = MockSession.return_value
        session.headers = {}
        resp_logon = MagicMock(status_code=200)
        resp_logon.json.return_value = LOGON_RESPONSE
        session.post.return_value = resp_logon

        session.get.side_effect = [
            _make_resp(FOLDER_50),              # resolve folder
            _make_resp(DOCUMENT_PARAMETERS),    # parameters
            _make_resp(DOCUMENT_DATAPROVIDERS), # dataproviders list
            _make_resp(DATAPROVIDER_DETAIL),    # DP0 detail
            _make_resp(DATAPROVIDER_QUERYPLAN), # DP0 queryplan
        ]
        return session

    def test_extract_parameters(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            self._setup_client(MockSession)

            doc = {"id": "100", "name": "Test Report", "description": "desc", "folderId": 50}
            with BoClient(bo_config) as client:
                report = client.extract_report(doc)

            assert len(report["parameters"]) == 3
            assert report["parameters"][0]["label"] == "Enter Start Date:"
            assert report["parameters"][0]["required"] is True
            assert report["parameters"][0]["select"] == "Single"
            assert report["parameters"][2]["required"] is False
            assert report["parameters"][2]["select"] == "Multiple"

    def test_extract_layout_columns(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            self._setup_client(MockSession)

            doc = {"id": "100", "name": "Test Report", "description": "desc", "folderId": 50}
            with BoClient(bo_config) as client:
                report = client.extract_report(doc)

            assert "Sales" in report["layout"]
            assert report["layout"]["Sales"]["columns"] == [
                "Retailer No.", "Retailer Name", "City", "Sales Amount"
            ]

    def test_extract_maps_folder_from_id(self, bo_config):
        with patch("bo_converter.bo_client.requests.Session") as MockSession:
            self._setup_client(MockSession)

            doc = {"id": "100", "name": "Test", "description": "", "folderId": 50}
            with BoClient(bo_config) as client:
                report = client.extract_report(doc)

            assert report["folder"] == "Sales Reports"
            assert report["folder_path"] == "Sales Reports"
            assert report["legacy_reports"] == "Sales Reports\\Test"
            assert report["name"] == "Test"
            assert report["report_format"] == "Paginated"
