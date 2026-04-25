"""Tests for TMDL builder edge cases."""

from model_generator.tmdl_builder import _col_block, to_title, classify_columns
from model_generator.snowflake_client import ColumnInfo
from model_generator.config import MeasureSuffix


def test_col_block_escapes_single_quotes():
    """A display name with a single quote must be doubled in the TMDL identifier."""
    result = _col_block(
        col_name="OWNER_S_NAME",
        data_type="string",
        hidden=False,
        display_name="Owner's Name",
    )
    assert "column 'Owner''s Name'" in result
    assert "sourceColumn: OWNER_S_NAME" in result


def test_col_block_no_quotes_when_no_space():
    """Column names without spaces should not be quoted."""
    result = _col_block(col_name="STATUS", data_type="string", hidden=False)
    assert "column STATUS" in result


def test_col_block_quoted_when_space():
    """Column names with spaces get single-quoted."""
    result = _col_block(
        col_name="FULL_NAME",
        data_type="string",
        hidden=False,
        display_name="Full Name",
    )
    assert "column 'Full Name'" in result


def test_col_block_only_quote_no_space():
    """A name with a quote but no space still gets quoted."""
    result = _col_block(
        col_name="IT_S_HERE",
        data_type="string",
        hidden=False,
        display_name="It's",
    )
    assert "column 'It''s'" in result


def test_to_title():
    assert to_title("SALES_COUNT") == "Sales Count"
    assert to_title("PLAYER_CARD_ONLINE_SALES_COUNT") == "Player Card Online Sales Count"
    assert to_title("ID") == "Id"


def test_classify_columns_key():
    cols = [ColumnInfo(name="DATE_KEY", sf_type="NUMBER", numeric_scale=0)]
    result = classify_columns(cols, [])
    assert result[0].kind == "key"
    assert result[0].tmdl_type == "int64"


def test_classify_columns_measure():
    cols = [ColumnInfo(name="SALES_COUNT", sf_type="NUMBER", numeric_scale=0)]
    suffixes = [MeasureSuffix("_COUNT", "int64", "0")]
    result = classify_columns(cols, suffixes)
    assert result[0].kind == "_COUNT"


def test_classify_columns_visible():
    cols = [ColumnInfo(name="STATUS", sf_type="TEXT", numeric_scale=0)]
    result = classify_columns(cols, [])
    assert result[0].kind == "visible"
    assert result[0].tmdl_type == "string"
