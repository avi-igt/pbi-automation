import os
import pytest
from bo_converter.config import BoConfig


def test_reads_bo_host(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text(
        "[bo]\n"
        "host = http://10.17.56.65:8080/biprws\n"
        "\n"
        "[datasource_keywords]\n"
        "default_datasource = semantic_model\n"
        "snowflake = rdst, tmir\n"
        "\n"
        "[model_keywords]\n"
        "MO_Sales = sales\n"
    )
    cfg = BoConfig(props)
    assert cfg.host == "http://10.17.56.65:8080/biprws"


def test_password_from_env(tmp_path, monkeypatch):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    monkeypatch.setenv("BO_PASSWORD", "secret123")
    cfg = BoConfig(props)
    assert cfg.password == "secret123"


def test_password_missing_raises(tmp_path, monkeypatch):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    monkeypatch.delenv("BO_PASSWORD", raising=False)
    cfg = BoConfig(props)
    with pytest.raises(ValueError, match="BO_PASSWORD"):
        _ = cfg.password


def test_username_from_config(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\nusername = admin\n")
    cfg = BoConfig(props)
    assert cfg.username == "admin"


def test_username_default(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    cfg = BoConfig(props)
    assert cfg.username == "Administrator"


def test_auth_type_default(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    cfg = BoConfig(props)
    assert cfg.auth_type == "secEnterprise"


def test_request_delay_default(tmp_path):
    props = tmp_path / "pbi.properties"
    props.write_text("[bo]\nhost = http://localhost:8080/biprws\n")
    cfg = BoConfig(props)
    assert cfg.request_delay == 0.2
