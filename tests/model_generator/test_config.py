"""Tests for model_generator config validation."""

import configparser
import pytest
from model_generator.config import _parse_dimension_value, _parse_model_section


def test_valid_dimension():
    result = _parse_dimension_value("dates", "DIMCORE.DATES, primary_key=DATE_KEY, strategy=A")
    assert result.schema == "DIMCORE"
    assert result.table == "DATES"
    assert result.primary_key == "DATE_KEY"
    assert result.strategy == "A"


def test_valid_dimension_strategy_b():
    result = _parse_dimension_value("locs", "DIMCORE.LOCATIONS, primary_key=LOCATION_KEY, strategy=B")
    assert result.strategy == "B"


def test_dimension_rejects_invalid_schema_chars():
    with pytest.raises(ValueError, match="alphanumeric"):
        _parse_dimension_value("bad", 'SCHEMA"; DROP.TABLE, primary_key=K, strategy=A')


def test_dimension_rejects_invalid_table_chars():
    with pytest.raises(ValueError, match="alphanumeric"):
        _parse_dimension_value("bad", 'GOOD_SCHEMA.TABLE"; DROP, primary_key=K, strategy=A')


def test_dimension_rejects_invalid_primary_key_chars():
    with pytest.raises(ValueError, match="alphanumeric"):
        _parse_dimension_value("bad", "SCHEMA.TABLE, primary_key=KEY'; --, strategy=A")


def test_dimension_missing_primary_key():
    with pytest.raises(ValueError, match="missing primary_key"):
        _parse_dimension_value("bad", "SCHEMA.TABLE, strategy=A")


def test_dimension_missing_dot():
    with pytest.raises(ValueError, match="SCHEMA.TABLE"):
        _parse_dimension_value("bad", "NOTABLE, primary_key=K, strategy=A")


def test_model_valid():
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp.read_string("""
[model.test]
display_name = Test LDI
fact_table = FINANCIAL.FINANCIAL_DAILY
dimensions = dates
""")
    result = _parse_model_section("test", cp, "model.test")
    assert result.fact_schema == "FINANCIAL"
    assert result.fact_table == "FINANCIAL_DAILY"


def test_model_rejects_invalid_fact_schema():
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp.read_string("""
[model.test]
display_name = Test LDI
fact_table = BAD"; DROP.TABLE
dimensions = dates
""")
    with pytest.raises(ValueError, match="alphanumeric"):
        _parse_model_section("test", cp, "model.test")


def test_model_rejects_invalid_fact_key_override():
    cp = configparser.ConfigParser(interpolation=None)
    cp.optionxform = str
    cp.read_string("""
[model.test]
display_name = Test LDI
fact_table = FINANCIAL.DAILY
dimensions = dates:BAD'KEY
""")
    with pytest.raises(ValueError, match="alphanumeric"):
        _parse_model_section("test", cp, "model.test")
