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
