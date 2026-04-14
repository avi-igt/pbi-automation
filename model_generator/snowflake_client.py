"""
snowflake_client.py — Snowflake connection and column introspection.

Usage:
    from model_generator.snowflake_client import SnowflakeClient
    from model_generator.config import load_config

    cfg = load_config()
    with SnowflakeClient(cfg.snowflake) as sf:
        columns = sf.get_columns("FINANCIAL", "FINANCIAL_DAILY")
        obj_type = sf.get_object_type("FINANCIAL", "FINANCIAL_DAILY")  # "View" or "Table"
"""

import os
import sys
from dataclasses import dataclass

import snowflake.connector
from snowflake.connector import DictCursor

from model_generator.config import SnowflakeConfig


# ---------------------------------------------------------------------------
# Data class
# ---------------------------------------------------------------------------

@dataclass
class ColumnInfo:
    name: str           # original Snowflake column name, e.g. SALES_COUNT
    sf_type: str        # raw Snowflake data type, e.g. NUMBER, TEXT, DATE
    numeric_scale: int  # 0 for integers, >0 for decimals


# ---------------------------------------------------------------------------
# Snowflake type → TMDL dataType mapping
# ---------------------------------------------------------------------------

_SF_TO_TMDL: dict[str, str] = {
    "NUMBER":        "int64",    # refined by scale in tmdl_builder
    "DECIMAL":       "decimal",
    "NUMERIC":       "decimal",
    "INT":           "int64",
    "INTEGER":       "int64",
    "BIGINT":        "int64",
    "SMALLINT":      "int64",
    "TINYINT":       "int64",
    "BYTEINT":       "int64",
    "FLOAT":         "double",
    "FLOAT4":        "double",
    "FLOAT8":        "double",
    "DOUBLE":        "double",
    "REAL":          "double",
    "TEXT":          "string",
    "VARCHAR":       "string",
    "CHAR":          "string",
    "CHARACTER":     "string",
    "STRING":        "string",
    "NCHAR":         "string",
    "NVARCHAR":      "string",
    "NVARCHAR2":     "string",
    "CHAR VARYING":  "string",
    "NCHAR VARYING": "string",
    "BINARY":        "binary",
    "VARBINARY":     "binary",
    "DATE":          "dateTime",
    "DATETIME":      "dateTime",
    "TIMESTAMP":     "dateTime",
    "TIMESTAMP_NTZ": "dateTime",
    "TIMESTAMP_LTZ": "dateTime",
    "TIMESTAMP_TZ":  "dateTime",
    "TIME":          "dateTime",
    "BOOLEAN":       "boolean",
    "VARIANT":       "string",
    "OBJECT":        "string",
    "ARRAY":         "string",
    "GEOGRAPHY":     "string",
    "GEOMETRY":      "string",
}


def sf_type_to_tmdl(sf_type: str, numeric_scale: int) -> str:
    """Map a Snowflake data type string to a TMDL dataType value.

    NUMBER with scale > 0 is treated as decimal; scale == 0 as int64.
    """
    sf_upper = sf_type.upper().strip()
    if sf_upper in ("NUMBER", "DECIMAL", "NUMERIC") and numeric_scale > 0:
        return "decimal"
    return _SF_TO_TMDL.get(sf_upper, "string")


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class SnowflakeClient:
    """Thin wrapper around snowflake-connector-python for column introspection."""

    def __init__(self, config: SnowflakeConfig):
        user = os.environ.get("SNOWFLAKE_USER", "")
        sso = config.authenticator.lower() != "snowflake"

        if not user:
            raise EnvironmentError(
                "SNOWFLAKE_USER environment variable not set.\n"
                "  export SNOWFLAKE_USER=your_username"
            )

        connect_kwargs: dict = dict(
            account=config.account,
            user=user,
            authenticator=config.authenticator,
            warehouse=config.warehouse,
            database=config.database,
            role=config.role,
            insecure_mode=False,
            client_session_keep_alive=False,
        )

        if not sso:
            # Password-based auth — require SNOWFLAKE_PASSWORD
            password = os.environ.get("SNOWFLAKE_PASSWORD", "")
            if not password:
                raise EnvironmentError(
                    "SNOWFLAKE_PASSWORD environment variable not set.\n"
                    "  export SNOWFLAKE_PASSWORD=your_password\n"
                    "  (or set authenticator = externalbrowser in semantic.properties for SSO)"
                )
            connect_kwargs["password"] = password

        auth_label = config.authenticator if sso else "password"
        print(
            f"  Connecting to Snowflake: {config.account} / {config.database} "
            f"[auth: {auth_label}] ...",
            file=sys.stderr,
        )
        self._conn = snowflake.connector.connect(**connect_kwargs)
        print("  Connected.", file=sys.stderr)

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def get_columns(self, schema: str, table: str) -> list[ColumnInfo]:
        """Return ordered column list for SCHEMA.TABLE from information_schema."""
        sql = """
            SELECT
                COLUMN_NAME,
                DATA_TYPE,
                COALESCE(NUMERIC_SCALE, 0) AS NUMERIC_SCALE
            FROM information_schema.columns
            WHERE table_schema = %(schema)s
              AND table_name   = %(table)s
            ORDER BY ordinal_position
        """
        cursor = self._conn.cursor(DictCursor)
        cursor.execute(sql, {"schema": schema.upper(), "table": table.upper()})
        rows = cursor.fetchall()

        if not rows:
            raise ValueError(
                f"No columns found for {schema}.{table}. "
                f"Check that the table/view exists in database "
                f"'{self._conn.database}'."
            )

        return [
            ColumnInfo(
                name=row["COLUMN_NAME"],
                sf_type=row["DATA_TYPE"],
                numeric_scale=int(row["NUMERIC_SCALE"] or 0),
            )
            for row in rows
        ]

    def get_object_type(self, schema: str, table: str) -> str:
        """Return 'View' or 'Table' for the given Snowflake object."""
        sql = """
            SELECT table_type
            FROM information_schema.tables
            WHERE table_schema = %(schema)s
              AND table_name   = %(table)s
        """
        cursor = self._conn.cursor(DictCursor)
        cursor.execute(sql, {"schema": schema.upper(), "table": table.upper()})
        row = cursor.fetchone()
        if not row:
            # Default to Table if object not found in tables view
            return "Table"
        raw = (row.get("TABLE_TYPE") or "BASE TABLE").upper()
        return "View" if "VIEW" in raw else "Table"

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def close(self) -> None:
        if self._conn:
            self._conn.close()

    def __enter__(self) -> "SnowflakeClient":
        return self

    def __exit__(self, *_) -> None:
        self.close()
