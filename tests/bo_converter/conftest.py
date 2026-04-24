import pytest
from bo_converter.config import BoConfig


@pytest.fixture
def bo_config(tmp_path, monkeypatch):
    props = tmp_path / "pbi.properties"
    props.write_text(
        "[bo]\n"
        "host = http://localhost:8080/biprws\n"
        "username = admin\n"
        "request_delay = 0\n"
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

DOCUMENTS_LIST = {
    "documents": {
        "document": [
            {
                "id": "100",
                "cuid": "Fabc123",
                "name": "Daily Sales Report",
                "description": "Shows daily sales by retailer",
                "folderId": 50,
                "scheduled": "false",
            },
            {
                "id": "101",
                "cuid": "Fdef456",
                "name": "RDST Summary",
                "description": "Snowflake RDST data",
                "folderId": 51,
                "scheduled": "false",
            },
        ]
    }
}

FOLDER_50 = {"id": "50", "name": "Sales Reports", "type": "Folder"}
FOLDER_51 = {"id": "51", "name": "Data Reports", "type": "Folder"}

DOCUMENT_PARAMETERS = {
    "parameters": {
        "parameter": [
            {
                "@optional": "false",
                "@type": "prompt",
                "id": 0,
                "name": "Enter Start Date:",
                "answer": {
                    "@constrained": "false",
                    "@type": "Date",
                    "info": {"@cardinality": "Single"},
                },
            },
            {
                "@optional": "false",
                "@type": "prompt",
                "id": 1,
                "name": "Enter End Date:",
                "answer": {
                    "@constrained": "false",
                    "@type": "Date",
                    "info": {"@cardinality": "Single"},
                },
            },
            {
                "@optional": "true",
                "@type": "prompt",
                "id": 2,
                "name": "Select Region:",
                "answer": {
                    "@constrained": "false",
                    "@type": "String",
                    "info": {"@cardinality": "Multiple"},
                },
            },
        ]
    }
}

DOCUMENT_DATAPROVIDERS = {
    "dataproviders": {
        "dataprovider": [
            {
                "id": "DP0",
                "name": "Sales",
                "dataSourceType": "unx",
            }
        ]
    }
}

DATAPROVIDER_DETAIL = {
    "dataprovider": {
        "id": "DP0",
        "name": "Sales",
        "dataSourceName": "LocationSales",
        "dataSourceType": "unx",
        "dictionary": {
            "expression": [
                {
                    "@dataType": "Numeric",
                    "@qualification": "Dimension",
                    "id": "DP0.DO6",
                    "name": "Retailer No.",
                },
                {
                    "@dataType": "String",
                    "@qualification": "Dimension",
                    "id": "DP0.DO7",
                    "name": "Retailer Name",
                },
                {
                    "@dataType": "String",
                    "@qualification": "Dimension",
                    "id": "DP0.DO8",
                    "name": "City",
                },
                {
                    "@dataType": "Numeric",
                    "@qualification": "Measure",
                    "id": "DP0.DOfa",
                    "name": "Sales Amount",
                },
            ]
        },
    }
}
