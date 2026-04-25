"""Tests for multi-site FRD parser config and parsing."""
import re
import pytest
from report_generator.config import PbiConfig


@pytest.fixture
def mo_config(tmp_path):
    """Missouri config — current defaults, nothing overridden."""
    props = tmp_path / "pbi.properties"
    props.write_text(
        "[fabric]\n"
        "workspace_name = Missouri - D1V1\n"
        "tenant_id = fake-tenant\n"
        "\n"
        "[site]\n"
        "site_prefix = MO\n"
        "sdt_aliases = Work Item\n"
        "skip_sections = Introduction, Performance Wizard Reporting\n"
        "logo_label = Missouri Lottery logo (top-left of header)\n"
    )
    return PbiConfig(props)


@pytest.fixture
def nj_config(tmp_path):
    """New Jersey config — different prefix and logo."""
    props = tmp_path / "pbi.properties"
    props.write_text(
        "[fabric]\n"
        "workspace_name = New Jersey - D1V1\n"
        "tenant_id = fake-tenant\n"
        "\n"
        "[site]\n"
        "site_prefix = NJ\n"
        "sdt_aliases = Work Item\n"
        "skip_sections = Introduction, Performance Wizard Reporting\n"
        "logo_label = New Jersey Lottery logo (top-left of header)\n"
    )
    return PbiConfig(props)


@pytest.fixture
def no_site_config(tmp_path):
    """Config with no [site] section — should fall back to MO defaults."""
    props = tmp_path / "pbi.properties"
    props.write_text(
        "[fabric]\n"
        "workspace_name = Missouri - D1V1\n"
        "tenant_id = fake-tenant\n"
    )
    return PbiConfig(props)


class TestSiteConfigLoading:
    def test_mo_prefix_regex(self, mo_config):
        assert mo_config.site_prefix_re.pattern == r"(?:MO)-\d+"
        assert mo_config.site_prefix_re.search("MO-12345 some text")
        assert not mo_config.site_prefix_re.search("NJ-12345 some text")

    def test_nj_prefix_regex(self, nj_config):
        assert nj_config.site_prefix_re.search("NJ-99999 some text")
        assert not nj_config.site_prefix_re.search("MO-12345 some text")

    def test_default_prefix_when_no_site_section(self, no_site_config):
        assert no_site_config.site_prefix_re.search("MO-12345")

    def test_sdt_aliases(self, mo_config):
        assert mo_config.sdt_aliases == {"Work Item"}

    def test_skip_sections(self, mo_config):
        assert mo_config.skip_sections == {"Introduction", "Performance Wizard Reporting"}

    def test_logo_label(self, mo_config):
        assert mo_config.logo_label == "Missouri Lottery logo (top-left of header)"

    def test_nj_logo_label(self, nj_config):
        assert nj_config.logo_label == "New Jersey Lottery logo (top-left of header)"

    def test_default_logo_label(self, no_site_config):
        assert "logo" in no_site_config.logo_label.lower()


from report_generator import frd_parser


class TestCleanWorkitemText:
    def test_strips_mo_prefix(self):
        raw = "MO-12345, Draft, Functional/Business - Some report text MO-12345a"
        result = frd_parser.clean_workitem_text(raw)
        assert "MO-12345" not in result
        assert "Some report text" in result

    def test_strips_nj_prefix(self, nj_config, monkeypatch):
        monkeypatch.setattr(frd_parser, "_cfg", nj_config)
        raw = "NJ-67890, Draft, Functional/Business - Some report text NJ-67890a"
        result = frd_parser.clean_workitem_text(raw)
        assert "NJ-67890" not in result
        assert "Some report text" in result

    def test_no_prefix_passthrough(self):
        result = frd_parser.clean_workitem_text("Plain text with no work items")
        assert result == "Plain text with no work items"


class TestParseSummary:
    def test_strips_mo_header(self):
        raw = "MO-111, Draft, Functional/Business - Report Title My Report Report Format Paginated"
        result = frd_parser.parse_summary(raw)
        assert result.get("Report Title") == "My Report"

    def test_strips_nj_header(self, nj_config, monkeypatch):
        monkeypatch.setattr(frd_parser, "_cfg", nj_config)
        raw = "NJ-222, Draft, Functional/Business - Report Title My Report Report Format Paginated"
        result = frd_parser.parse_summary(raw)
        assert result.get("Report Title") == "My Report"


class TestParseRequirements:
    def test_extracts_mo_work_item(self):
        raw = "MO-100, Draft, Functional/Business - Must show total sales MO-100"
        result = frd_parser.parse_requirements([raw])
        assert len(result) == 1
        assert result[0]["id"] == "MO-100"
        assert "total sales" in result[0]["text"]

    def test_extracts_nj_work_item(self, nj_config, monkeypatch):
        monkeypatch.setattr(frd_parser, "_cfg", nj_config)
        raw = "NJ-200, Draft, Functional/Business - Must show total sales NJ-200"
        result = frd_parser.parse_requirements([raw])
        assert len(result) == 1
        assert result[0]["id"] == "NJ-200"
        assert "total sales" in result[0]["text"]
