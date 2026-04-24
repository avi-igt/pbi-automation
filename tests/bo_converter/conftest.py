import pytest
from bo_converter.config import BoConfig


@pytest.fixture
def bo_config(tmp_path, monkeypatch):
    props = tmp_path / "pbi.properties"
    props.write_text(
        "[bo]\n"
        "host = http://localhost:8080/biprws\n"
        "username = admin\n"
        "\n"
        "[datasource_keywords]\n"
        "default_datasource = semantic_model\n"
        "snowflake = rdst, tmir\n"
        "db2 = claims, payments\n"
        "\n"
        "[model_keywords]\n"
        "MO_Sales = sales\n"
    )
    monkeypatch.setenv("BO_PASSWORD", "testpass")
    return BoConfig(props)


LOGON_RESPONSE = {
    "logonToken": "COMMANDCOM-LCM:6400@{3&2=5291,U3&p=40674.9}",
}

INFOSTORE_PAGE1 = {
    "entries": {
        "entry": [
            {
                "SI_ID": 100,
                "SI_NAME": "Daily Sales Report",
                "SI_DESCRIPTION": "Shows daily sales by retailer",
                "SI_PATH": "Public Folders/Sales Reports/Daily Sales Report",
                "SI_KIND": "Webi",
                "SI_PARENT_FOLDER": 50,
            },
            {
                "SI_ID": 101,
                "SI_NAME": "RDST Summary",
                "SI_DESCRIPTION": "Snowflake RDST data",
                "SI_PATH": "Public Folders/Data Reports/RDST Summary",
                "SI_KIND": "Webi",
                "SI_PARENT_FOLDER": 51,
            },
        ]
    }
}

DOCUMENT_PARAMETERS = {
    "parameters": {
        "parameter": [
            {
                "id": 0,
                "name": "Enter Start Date:",
                "type": "DateTime",
                "mandatory": True,
                "multiValue": False,
            },
            {
                "id": 1,
                "name": "Enter End Date:",
                "type": "DateTime",
                "mandatory": True,
                "multiValue": False,
            },
            {
                "id": 2,
                "name": "Select Region:",
                "type": "String",
                "mandatory": False,
                "multiValue": True,
            },
        ]
    }
}

DOCUMENT_DATAPROVIDERS = {
    "dataproviders": {
        "dataprovider": [
            {
                "id": "DP0",
                "name": "Query 1",
                "dataSourceName": "Sales Universe",
                "dataSourceType": "unx",
            }
        ]
    }
}

DOCUMENT_REPORTS = {
    "reports": {
        "report": [
            {"id": 1, "name": "Report 1"},
        ]
    }
}

DOCUMENT_ELEMENTS = {
    "reportElements": {
        "reportElement": [
            {
                "id": "table1",
                "type": "Table",
                "name": "Block 1",
                "headers": {
                    "header": [
                        {"name": "Retailer No."},
                        {"name": "Retailer Name"},
                        {"name": "City"},
                        {"name": "Sales Amount"},
                    ]
                },
            }
        ]
    }
}
