"""
report_builder.py — builds the companion .Report folder content for a semantic model.

Every generated report is an intentional placeholder:
  - One page, 1280x720
  - Single textbox visual confirming this file represents the data model
  - Binds to the companion .SemanticModel via definition.pbir byPath reference

No visuals, measures, or report-level formatting are generated here.  The
placeholder establishes the Fabric item pairing so Power BI Desktop and ALM
Toolkit treat the report as a sibling of the semantic model.

All functions return strings.  No file I/O here — writing is handled by
model_generator.py.
"""

import json
import uuid

from model_generator.config import ModelDef

_THEME_NAME = "CY24SU10"


# ---------------------------------------------------------------------------
# ID helpers
# ---------------------------------------------------------------------------

def _new_id() -> str:
    """Return a UUID without hyphens, matching the page/visual ID convention."""
    return uuid.uuid4().hex


# ---------------------------------------------------------------------------
# definition.pbir
# ---------------------------------------------------------------------------

def build_definition_pbir(model_def: ModelDef) -> str:
    """Bind this report to its companion SemanticModel via relative byPath."""
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definitionProperties/2.0.0/schema.json"
        ),
        "version": "4.0",
        "datasetReference": {
            "byPath": {
                "path": f"../{model_def.display_name}.SemanticModel"
            }
        },
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# .platform
# ---------------------------------------------------------------------------

def build_report_platform_json(model_def: ModelDef) -> str:
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/"
            "gitIntegration/platformProperties/2.0.0/schema.json"
        ),
        "metadata": {
            "type": "Report",
            "displayName": model_def.display_name,
        },
        "config": {
            "version": "2.0",
            "logicalId": str(uuid.uuid4()),
        },
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# definition/version.json
# ---------------------------------------------------------------------------

def build_version_json() -> str:
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/versionMetadata/1.0.0/schema.json"
        ),
        "version": "2.0.0",
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# definition/report.json
# ---------------------------------------------------------------------------

def build_report_json() -> str:
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/report/3.0.0/schema.json"
        ),
        "themeCollection": {
            "baseTheme": {
                "name": _THEME_NAME,
                "reportVersionAtImport": {
                    "visual": "1.8.95",
                    "report": "2.0.95",
                    "page": "1.3.95",
                },
                "type": "SharedResources",
            }
        },
        "objects": {
            "section": [
                {
                    "properties": {
                        "verticalAlignment": {
                            "expr": {"Literal": {"Value": "'Top'"}}
                        }
                    }
                }
            ],
            "outspacePane": [
                {
                    "properties": {
                        "expanded": {
                            "expr": {"Literal": {"Value": "true"}}
                        }
                    }
                }
            ],
        },
        "resourcePackages": [
            {
                "name": "SharedResources",
                "type": "SharedResources",
                "items": [
                    {
                        "name": _THEME_NAME,
                        "path": f"BaseThemes/{_THEME_NAME}.json",
                        "type": "BaseTheme",
                    }
                ],
            }
        ],
        "settings": {
            "useStylableVisualContainerHeader": True,
            "exportDataMode": "AllowSummarized",
            "defaultDrillFilterOtherVisuals": True,
            "allowChangeFilterTypes": True,
            "useEnhancedTooltips": True,
            "useDefaultAggregateDisplayName": True,
        },
        "slowDataSourceSettings": {
            "isCrossHighlightingDisabled": False,
            "isSlicerSelectionsButtonEnabled": False,
            "isFilterSelectionsButtonEnabled": False,
            "isFieldWellButtonEnabled": False,
            "isApplyAllButtonEnabled": False,
        },
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# definition/pages/pages.json
# ---------------------------------------------------------------------------

def build_pages_json(page_id: str) -> str:
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/pagesMetadata/1.0.0/schema.json"
        ),
        "pageOrder": [page_id],
        "activePageName": page_id,
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# definition/pages/<pageId>/page.json
# ---------------------------------------------------------------------------

def build_page_json(page_id: str, model_def: ModelDef) -> str:
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/page/2.0.0/schema.json"
        ),
        "name": page_id,
        "displayName": f"{model_def.display_name} Dataset",
        "displayOption": "FitToPage",
        "height": 720,
        "width": 1280,
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# definition/pages/<pageId>/visuals/<visualId>/visual.json
# ---------------------------------------------------------------------------

def build_placeholder_visual(visual_id: str, model_def: ModelDef) -> str:
    """Single full-width textbox explaining this report is an intentional placeholder."""
    message = (
        f"The page/report is intentionally left blank. "
        f"This Power BI file represents the '{model_def.display_name}' "
        f"data model for MO Lottery."
    )
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/definition/visualContainer/2.4.0/schema.json"
        ),
        "name": visual_id,
        "position": {
            "x": 14,
            "y": 148,
            "z": 0,
            "height": 299,
            "width": 1244,
            "tabOrder": 0,
        },
        "visual": {
            "visualType": "textbox",
            "objects": {
                "general": [
                    {
                        "properties": {
                            "paragraphs": [
                                {
                                    "textRuns": [
                                        {
                                            "value": message,
                                            "textStyle": {"fontSize": "28pt"},
                                        }
                                    ]
                                }
                            ]
                        }
                    }
                ]
            },
            "drillFilterOtherVisuals": True,
        },
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# .pbi/localSettings.json
# ---------------------------------------------------------------------------

def build_local_settings_json() -> str:
    """Minimal localSettings — no remoteArtifacts until the report is published."""
    payload = {
        "$schema": (
            "https://developer.microsoft.com/json-schemas/fabric/item/"
            "report/localSettings/1.0.0/schema.json"
        )
    }
    return json.dumps(payload, indent=2)


# ---------------------------------------------------------------------------
# Convenience: return all IDs needed by model_generator
# ---------------------------------------------------------------------------

def new_report_ids() -> tuple[str, str]:
    """Return (page_id, visual_id) as fresh hex UUIDs."""
    return _new_id(), _new_id()
