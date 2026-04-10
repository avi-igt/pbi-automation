"""
config.py — reads pbi.properties and exposes Fabric / RDL configuration.

Usage:
    from src.config import cfg
    cs = cfg.connect_string("MO_Sales")
    logo = cfg.logo_b64           # base64 PNG or "" if template not found
"""

import configparser
import re
import os
from pathlib import Path

# Repository root = directory containing this file's parent
_REPO_ROOT = Path(__file__).parent.parent

_PROPERTIES_FILE = _REPO_ROOT / "pbi.properties"
_FALLBACK_TEMPLATE = _REPO_ROOT / "templates" / "MO_Report_Template.rdl"


class PbiConfig:
    """Loaded once at import time; use the module-level `cfg` singleton."""

    def __init__(self):
        self._cp = configparser.ConfigParser(interpolation=None)
        if _PROPERTIES_FILE.exists():
            self._cp.read(_PROPERTIES_FILE, encoding="utf-8")

        self.workspace_name = self._get("fabric", "workspace_name", "Missouri - D1V1")
        self.tenant_id = self._get("fabric", "tenant_id", "TODO_TENANT_ID")

        # Dataset GUID map  { "MO_Sales": "45ddd7fc-..." }
        self.dataset_guids: dict[str, str] = {}
        if self._cp.has_section("datasets"):
            for k, v in self._cp.items("datasets"):
                # Normalise key to PascalCase "MO_Sales" etc.
                self.dataset_guids[k.upper().replace(" ", "_")] = v.strip()

        # Page / layout defaults
        self.page_width = self._get("rdl", "page_width", "11in")
        self.page_height = self._get("rdl", "page_height", "8.5in")
        self.margin = self._get("rdl", "margin", "0.2in")
        self.header_height = self._get("rdl", "header_height", "0.90563in")
        self.footer_height = self._get("rdl", "footer_height", "0.42486in")
        self.default_font = self._get("rdl", "default_font", "Segoe UI")

        # Embedded logo base64 (extracted from template RDL on first access)
        self._logo_b64: str | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get(self, section: str, key: str, default: str) -> str:
        try:
            return self._cp.get(section, key).strip()
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def get_dataset_guid(self, model_name: str) -> str:
        """Return the Fabric dataset GUID for *model_name* (e.g. 'MO_Sales').
        Returns 'TODO_GUID' if not configured yet."""
        key = model_name.strip().upper().replace(" ", "_").replace("-", "_")
        return self.dataset_guids.get(key, f"TODO_GUID_{model_name}")

    def connect_string(self, model_name: str) -> str:
        """Build the Power BI Fabric ConnectString for *model_name*."""
        guid = self.get_dataset_guid(model_name)
        return (
            f'Data Source=pbiazure://api.powerbi.com/;'
            f'Identity Provider="https://login.microsoftonline.com/organizations, '
            f'https://analysis.windows.net/powerbi/api, {self.tenant_id}";'
            f'Initial Catalog=sobe_wowvirtualserver-{guid};'
            f'Integrated Security=ClaimsToken'
        )

    def datasource_name(self, model_name: str) -> str:
        """Return the canonical DataSource Name for *model_name*."""
        ws_slug = self.workspace_name.replace(" ", "").replace("-", "")
        return f"{ws_slug}_{model_name}"

    # ------------------------------------------------------------------
    # Logo extraction
    # ------------------------------------------------------------------

    @property
    def logo_b64(self) -> str:
        """Base64 PNG data for the MO Lottery logo (molotterylogov).
        Returns empty string if the template RDL is not present."""
        if self._logo_b64 is None:
            self._logo_b64 = self._load_logo()
        return self._logo_b64

    def _load_logo(self) -> str:
        template_path = _FALLBACK_TEMPLATE
        rdl_template_setting = self._get("paths", "rdl_template", "")
        if rdl_template_setting:
            candidate = Path(rdl_template_setting)
            if not candidate.is_absolute():
                candidate = _REPO_ROOT / candidate
            if candidate.exists():
                template_path = candidate

        if not template_path.exists():
            return ""

        content = template_path.read_text(encoding="utf-8", errors="replace")
        # Extract <EmbeddedImage Name="molotterylogov"> ... <ImageData>DATA</ImageData>
        m = re.search(
            r'<EmbeddedImage\s+Name="molotterylogov">'
            r'[\s\S]*?<ImageData>([\s\S]*?)</ImageData>',
            content,
        )
        if m:
            return m.group(1).strip()
        return ""


# Module-level singleton
cfg = PbiConfig()
