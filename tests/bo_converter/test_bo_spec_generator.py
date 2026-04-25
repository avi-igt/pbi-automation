import json
from pathlib import Path
import pytest

from bo_converter.bo_spec_generator import generate_specs_from_json


SAMPLE_EXTRACTED = {
    "source": "http://localhost:8080/biprws",
    "total_reports": 1,
    "extracted_count": 1,
    "error_count": 0,
    "errors": [],
    "reports": [
        {
            "folder": "Sales Reports",
            "name": "Daily Sales Report",
            "report_format": "Paginated",
            "legacy_reports": "Public Folders\\Sales Reports\\Daily Sales Report",
            "legacy_users": "",
            "summary": "Shows daily sales by retailer",
            "sort": "N/A",
            "target_folder": "Sales Reports",
            "notes": "",
            "datasource_type": "semantic_model",
            "parameters": [
                {"label": "Start Date", "required": True, "select": "Single", "notes": ""},
                {"label": "End Date", "required": True, "select": "Single", "notes": ""},
            ],
            "filters": [],
            "layout": {
                "main": {
                    "columns": ["Retailer No.", "Retailer Name", "City", "Sales Amount"],
                    "raw": "",
                }
            },
            "requirements": [],
            "_dataproviders": [
                {"name": "Query 1", "dataSourceName": "Sales Universe", "dataSourceType": "unx"}
            ],
        }
    ],
}


def test_generates_md_files(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)

    assert len(paths) == 1
    assert paths[0].exists()
    content = paths[0].read_text()
    assert "# RDL Report Spec:" in content
    assert "Daily Sales Report" in content


def test_spec_contains_parameters(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)
    content = paths[0].read_text()

    assert "Start Date" in content
    assert "End Date" in content


def test_spec_contains_layout_columns(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)
    content = paths[0].read_text()

    assert "Retailer No." in content
    assert "Sales Amount" in content


def test_spec_contains_legacy_path(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)
    content = paths[0].read_text()

    assert "Public Folders" in content


def test_filename_is_slugified(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)

    assert paths[0].name == "daily-sales-report.md"


def test_spec_contains_legacy_universes(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir)
    content = paths[0].read_text()

    assert "Legacy Universe(s):" in content
    assert "`Sales Universe`" in content


def test_universe_map_overrides_datasource_type(tmp_path):
    """When universe_map matches a dataprovider, it wins over datasource_type."""
    import copy
    data = copy.deepcopy(SAMPLE_EXTRACTED)
    data["reports"][0]["datasource_type"] = "semantic_model"
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(data))
    output_dir = tmp_path / "specs"

    universe_map = {"sales universe": "db2"}
    paths = generate_specs_from_json(json_path, output_dir, universe_map=universe_map)
    content = paths[0].read_text()

    assert "DB2" in content


def test_universe_map_model_name_sets_semantic_model(tmp_path):
    """When universe_map value is a model name (not a ds_type), implies semantic_model."""
    import copy
    data = copy.deepcopy(SAMPLE_EXTRACTED)
    data["reports"][0]["datasource_type"] = ""
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(data))
    output_dir = tmp_path / "specs"

    universe_map = {"sales universe": "MO_Sales"}
    paths = generate_specs_from_json(json_path, output_dir, universe_map=universe_map)
    content = paths[0].read_text()

    assert "MO_Sales" in content
    assert "PBIDATASET" in content


def test_universe_map_miss_falls_through(tmp_path):
    """When universe_map has no match, falls through to datasource_type."""
    import copy
    data = copy.deepcopy(SAMPLE_EXTRACTED)
    data["reports"][0]["datasource_type"] = "snowflake"
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(data))
    output_dir = tmp_path / "specs"

    universe_map = {"other universe": "db2"}
    paths = generate_specs_from_json(json_path, output_dir, universe_map=universe_map)
    content = paths[0].read_text()

    assert "Snowflake" in content


def test_skips_reports_with_filter(tmp_path):
    json_path = tmp_path / "bo_extracted.json"
    json_path.write_text(json.dumps(SAMPLE_EXTRACTED))
    output_dir = tmp_path / "specs"

    paths = generate_specs_from_json(json_path, output_dir, report_filter="NONEXISTENT")

    assert len(paths) == 0
