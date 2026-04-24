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
