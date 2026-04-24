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
            session.headers = {}
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
