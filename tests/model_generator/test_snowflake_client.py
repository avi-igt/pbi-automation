"""Tests that SnowflakeClient properly closes cursors after queries."""

from unittest.mock import MagicMock, patch
import pytest

from model_generator.snowflake_client import SnowflakeClient
from model_generator.config import SnowflakeConfig


@pytest.fixture
def sf_config():
    return SnowflakeConfig(
        account="test-account",
        warehouse="test-wh",
        database="test-db",
        role="test-role",
        authenticator="snowflake",
    )


@pytest.fixture
def mock_conn():
    conn = MagicMock()
    cursor = MagicMock()
    conn.cursor.return_value = cursor
    return conn, cursor


@patch.dict("os.environ", {"SNOWFLAKE_USER": "testuser", "SNOWFLAKE_PASSWORD": "testpass"})
@patch("model_generator.snowflake_client.snowflake.connector.connect")
def test_get_columns_closes_cursor(mock_connect, sf_config, mock_conn):
    conn, cursor = mock_conn
    mock_connect.return_value = conn
    cursor.fetchall.return_value = [
        {"COLUMN_NAME": "ID", "DATA_TYPE": "NUMBER", "NUMERIC_SCALE": 0},
    ]

    client = SnowflakeClient(sf_config)
    result = client.get_columns("SCHEMA", "TABLE")

    cursor.close.assert_called_once()
    assert len(result) == 1
    assert result[0].name == "ID"


@patch.dict("os.environ", {"SNOWFLAKE_USER": "testuser", "SNOWFLAKE_PASSWORD": "testpass"})
@patch("model_generator.snowflake_client.snowflake.connector.connect")
def test_get_columns_closes_cursor_on_error(mock_connect, sf_config, mock_conn):
    conn, cursor = mock_conn
    mock_connect.return_value = conn
    cursor.fetchall.return_value = []

    client = SnowflakeClient(sf_config)
    with pytest.raises(ValueError, match="No columns found"):
        client.get_columns("SCHEMA", "TABLE")

    cursor.close.assert_called_once()


@patch.dict("os.environ", {"SNOWFLAKE_USER": "testuser", "SNOWFLAKE_PASSWORD": "testpass"})
@patch("model_generator.snowflake_client.snowflake.connector.connect")
def test_get_object_type_closes_cursor(mock_connect, sf_config, mock_conn):
    conn, cursor = mock_conn
    mock_connect.return_value = conn
    cursor.fetchone.return_value = {"TABLE_TYPE": "VIEW"}

    client = SnowflakeClient(sf_config)
    result = client.get_object_type("SCHEMA", "TABLE")

    cursor.close.assert_called_once()
    assert result == "View"


@patch.dict("os.environ", {"SNOWFLAKE_USER": "testuser", "SNOWFLAKE_PASSWORD": "testpass"})
@patch("model_generator.snowflake_client.snowflake.connector.connect")
def test_get_object_type_closes_cursor_when_not_found(mock_connect, sf_config, mock_conn):
    conn, cursor = mock_conn
    mock_connect.return_value = conn
    cursor.fetchone.return_value = None

    client = SnowflakeClient(sf_config)
    result = client.get_object_type("SCHEMA", "TABLE")

    cursor.close.assert_called_once()
    assert result == "Table"
