"""
config.py — reads pbi.properties and exposes Fabric / RDL configuration.

Usage:
    from report_generator.config import cfg
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
_PKG_ROOT = Path(__file__).parent
_FALLBACK_TEMPLATE = _PKG_ROOT / "templates" / "MO_Report_Template.rdl"


class PbiConfig:
    """Loaded once at import time; use the module-level `cfg` singleton."""

    def __init__(self):
        self._cp = configparser.ConfigParser(interpolation=None)
        self._cp.optionxform = str  # preserve key case (needed for MO_Sales etc.)
        if _PROPERTIES_FILE.exists():
            self._cp.read(_PROPERTIES_FILE, encoding="utf-8")

        self.workspace_name = self._get("fabric", "workspace_name", "Missouri - D1V1")
        self.tenant_id = self._get("fabric", "tenant_id", "TODO_TENANT_ID")

        # Dataset GUID map  { "MO_SALES": "45ddd7fc-..." }  (keys uppercased for lookup)
        self.dataset_guids: dict[str, str] = {}
        if self._cp.has_section("datasets"):
            for k, v in self._cp.items("datasets"):
                self.dataset_guids[k.upper().replace(" ", "_")] = v.strip()

        # ODBC data sources (Lane 3 — paginated reports / batch exports only)
        self.db2_source_name = self._get("odbc", "db2_source_name", "BOADB")
        self.db2_dsn = self._get("odbc", "db2_dsn", "MOS-Q1-BOADB")
        self.sfodbc_source_name = self._get("odbc", "sfodbc_source_name", "LPC_E2_SFODBC")
        self.sfodbc_dsn = self._get("odbc", "sfodbc_dsn", "MOS-PX-SFODBC")

        # Snowflake native connector (ADBC 2.0) — Lane 1 / Lane 2 only
        self.sf_native_host = self._get(
            "snowflake_native", "host", "TODO_SF_NATIVE_HOST"
        )
        self.sf_native_implementation = self._get(
            "snowflake_native", "implementation", "2.0"
        )

        # Datasource type detection — ordered list of (ds_type, [keywords])
        # e.g. [("snowflake", ["rdst", "tmir", ...]), ("db2", ["claims", ...])]
        # The reserved key "default_datasource" is excluded from keyword matching
        # and is used as the fallback when no keyword matches.
        _VALID_DS = {"snowflake", "db2", "semantic_model"}
        _raw_default = self._get("datasource_keywords", "default_datasource", "semantic_model").lower()
        self._default_datasource: str = _raw_default if _raw_default in _VALID_DS else "semantic_model"
        self._datasource_keywords: list[tuple[str, list[str]]] = [
            (ds, kws)
            for ds, kws in self._parse_kw_section("datasource_keywords")
            if ds.lower() != "default_datasource"
        ]

        # Semantic model selection — ordered list of (model_name, [keywords])
        # e.g. [("MO_LVMTransactional", ["lvm transaction", ...]), ...]
        self._model_keywords: list[tuple[str, list[str]]] = (
            self._parse_kw_section("model_keywords")
        )

        # Page / layout defaults
        self.page_width = self._get("rdl", "page_width", "11in")
        self.page_height = self._get("rdl", "page_height", "8.5in")
        self.margin = self._get("rdl", "margin", "0.2in")
        self.header_height = self._get("rdl", "header_height", "0.90563in")
        self.footer_height = self._get("rdl", "footer_height", "0.42486in")
        self.default_font = self._get("rdl", "default_font", "Segoe UI")
        self.title_font = self._get("rdl", "title_font", "Segoe UI Light")
        self.title_font_size = self._get("rdl", "title_font_size", "14pt")
        self.timezone = self._get("rdl", "timezone", "Central Standard Time")

        # PBIP canvas and branding
        self.canvas_width = int(self._get("pbip", "canvas_width", "1280"))
        self.canvas_height = int(self._get("pbip", "canvas_height", "720"))
        self.theme_name = self._get("pbip", "theme_name", "CY22SU08")
        self.brand_color_grid = self._get("pbip", "brand_color_grid", "#D6DBEA")
        self.brand_color_header = self._get("pbip", "brand_color_header", "#FAFAFA")

        # Directory containing hand-authored SQL files for ODBC reports
        _sql_dir_raw = self._get("paths", "sql_dir", "sql")
        _sql_dir_path = Path(_sql_dir_raw)
        self.sql_dir: Path = (
            _sql_dir_path if _sql_dir_path.is_absolute() else _PKG_ROOT / _sql_dir_path
        )

        # Embedded logo base64 (extracted from template RDL on first access)
        self._logo_b64: str | None = None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _parse_kw_section(self, section: str) -> list[tuple[str, list[str]]]:
        """Parse a comma-separated keyword section into an ordered list of
        (key, [keyword, ...]) tuples.  Keywords are lowercased for matching."""
        if not self._cp.has_section(section):
            return []
        result = []
        for key, val in self._cp.items(section):
            keywords = [kw.strip().lower() for kw in val.split(",") if kw.strip()]
            if keywords:
                result.append((key, keywords))
        return result

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
        model_slug = model_name.replace(" ", "_")
        return f"{ws_slug}_{model_slug}"

    def snowflake_native_m_expr(
        self,
        database: str = "",
        warehouse: str = "",
    ) -> str:
        """Return the Power Query M expression for the Snowflake native (ADBC 2.0) connector.

        Approved for Lane 1 / Lane 2 workloads: semantic models and DirectQuery.
        Do NOT use for paginated reports (RDL) — those use sfodbc_dsn (Lane 3).

        Args:
            database:  Optional Snowflake database name to include in the options record.
            warehouse: Optional Snowflake warehouse name to include in the options record.

        Example output (no optional args):
            Snowflake.Databases(
                "igtgloballottery-igtpxv1_ldi.privatelink.snowflakecomputing.com",
                [Implementation = "2.0"]
            )
        """
        opts: list[str] = [f'Implementation = "{self.sf_native_implementation}"']
        if warehouse:
            opts.append(f'Warehouse = "{warehouse}"')
        if database:
            opts.append(f'Database = "{database}"')
        opts_str = ", ".join(opts)
        return (
            f'Snowflake.Databases(\n'
            f'    "{self.sf_native_host}",\n'
            f'    [{opts_str}]\n'
            f')'
        )

    # ------------------------------------------------------------------
    # Datasource inference  (driven by pbi.properties keyword tables)
    # ------------------------------------------------------------------

    def infer_datasource(self, report: dict) -> str:
        """Return 'snowflake', 'db2', or 'semantic_model' for *report*.

        Matches the combined name + summary + notes + legacy_reports text
        against [datasource_keywords] in pbi.properties.  First matching
        key wins; falls back to 'semantic_model' if no keyword matches.
        """
        # legacy_reports is a BO folder path — not a data-source indicator.
        # Limiting to name + summary + notes avoids false positives like
        # reports stored under a "Security" BO folder being flagged as Snowflake.
        text = " ".join([
            report.get("name", ""),
            report.get("summary", ""),
            report.get("notes", ""),
        ]).lower()
        for ds_type, keywords in self._datasource_keywords:
            if any(kw in text for kw in keywords):
                return ds_type
        return self._default_datasource

    def infer_semantic_model(self, report: dict) -> str:
        """Return the best-matching semantic model name for *report*.

        Matches the report name + summary against [model_keywords] in
        pbi.properties.  First matching model wins.  When nothing matches,
        returns the last model listed in [model_keywords] (put the broadest
        dataset last in the file).  Falls back to the first key in [datasets]
        if [model_keywords] is empty, or 'TODO_SemanticModel' if neither is set.
        """
        text = (report.get("name", "") + " " + report.get("summary", "")).lower()
        for model, keywords in self._model_keywords:
            if any(kw in text for kw in keywords):
                return model
        # Default: last model in [model_keywords] (broadest / catch-all)
        if self._model_keywords:
            return self._model_keywords[-1][0]
        # Last resort: first dataset configured in [datasets]
        if self.dataset_guids:
            return next(iter(self.dataset_guids))
        return "TODO_SemanticModel"

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
                candidate = _PKG_ROOT / candidate
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
