"""
rdl_generator.py
Generates .rdl (Report Definition Language) XML for paginated Power BI reports.

Improvements:
- Reads connection strings / dataset GUIDs from pbi.properties via config.py
- Production-matching header: MO Lottery logo + report title + run datetime + date range
- Production-matching footer: report name + overall page number
- Hidden ExecDateTime parameter with Code.GetCST() VB function
- Embedded molotterylogov logo PNG (extracted from template RDL)
- Correct RDL structure with cl namespace for ComponentMetadata
- PBIDATASET connector with real Fabric ConnectStrings
- ODBC/DB2 fallback for legacy DB reports
"""

import json
import re
import uuid
from html import escape as _xml_escape
from pathlib import Path
from datetime import datetime

# RDL namespaces matching real Power BI Report Builder output
RDL_NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RDL_RD = "http://schemas.microsoft.com/SQLServer/reporting/reportdesigner"
RDL_DF = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition/defaultfontfamily"
RDL_AM = "http://schemas.microsoft.com/sqlserver/reporting/authoringmetadata"
RDL_CL = "http://schemas.microsoft.com/sqlserver/reporting/2010/01/componentdefinition"


def safe_name(text: str) -> str:
    """Convert arbitrary text to a safe XML/field identifier."""
    return re.sub(r"\W+", "_", text).strip("_")


def _load_sql(report_name: str) -> str | None:
    """Return the contents of sql/{safe_name}.sql if the file exists, else None.

    The SQL file name is derived from the report name using the same sanitisation
    applied to .rdl output filenames:  non-word chars stripped, spaces → underscores.
    Example:  "1042 Tax"  →  sql/1042_Tax.sql

    The file may contain any valid SQL for the target ODBC source (DB2 or Snowflake).
    Positional ? parameters must appear in the same order as the report's parameters.
    If the file is absent the generator falls back to an auto-generated stub.
    """
    c = _get_cfg()
    if c is None:
        return None
    safe = re.sub(r"[^\w\s\-]", "", report_name).strip().replace(" ", "_")
    sql_file = c.sql_dir / f"{safe}.sql"
    if sql_file.exists():
        return sql_file.read_text(encoding="utf-8")
    return None


def safe_comment(text: str) -> str:
    """Sanitize text for embedding inside an XML comment — replace '--' sequences."""
    return text.replace("--", "\u2013\u2013")  # replace with en-dashes to preserve meaning


def xe(text: str) -> str:
    """XML-escape text for embedding in element content (escapes &, <, >, \", ')."""
    return _xml_escape(str(text), quote=False)


try:
    from report_generator.config import cfg as _cfg
except ImportError:
    try:
        from config import cfg as _cfg  # when run directly
    except ImportError:
        _cfg = None  # no config available


def _get_cfg():
    return _cfg


def guess_semantic_model(report: dict) -> str:
    """Return the best-matching semantic model name for *report*.

    Checks ``report['_spec_model']`` first (set by spec_parser when the spec
    confirms the model explicitly), then delegates to cfg.infer_semantic_model()
    which reads [model_keywords] from pbi.properties.
    """
    if report.get("_spec_model"):
        return report["_spec_model"]
    c = _get_cfg()
    if c is not None:
        return c.infer_semantic_model(report)
    return "TODO_SemanticModel"


def make_parameter_xml(param: dict) -> tuple:
    """
    Generate RDL <ReportParameter> XML and a matching <QueryParameter> stub.
    Returns (report_parameter_xml, query_parameter_xml).
    """
    label = param.get("label", "Param")
    name = safe_name(label)
    required = param.get("required", False)
    multi = param.get("select", "Single").lower() == "multiple"
    notes = param.get("notes", "")

    nullable = "false" if required else "true"
    multi_xml = "<MultiValue>true</MultiValue>" if multi else ""

    default = ""
    default_match = re.search(r"Default[:\s]+(.+?)(?:\.|,|$)", notes, re.IGNORECASE)
    if default_match and not multi:
        dval = default_match.group(1).strip()
        default = f"""
      <DefaultValue>
        <Values><Value>{xe(dval)}</Value></Values>
      </DefaultValue>"""

    report_param = f"""    <ReportParameter Name="{name}">
      <DataType>String</DataType>
      <Nullable>{nullable}</Nullable>
      {multi_xml}
      <Prompt>{xe(label)}</Prompt>{default}
    </ReportParameter>"""

    query_param = f"""          <QueryParameter Name="@{name}">
            <Value>=Parameters!{name}.Value</Value>
          </QueryParameter>"""

    return report_param, query_param


def make_dax_query(report_name: str, columns: list, dataset_name: str) -> str:
    """
    Build a DAX EVALUATE SUMMARIZECOLUMNS stub for semantic model reports.
    Columns are placed as TODO placeholders — developer fills in actual table/measure names.
    """
    # Group dimension-looking cols vs measure-looking cols
    measure_keywords = re.compile(
        r"amount|count|total|avg|average|sum|sales|net|gross|pct|%|rate|qty|quantity", re.I
    )
    dims = []
    measures = []
    for col in columns:
        if measure_keywords.search(col):
            measures.append(col)
        else:
            dims.append(col)

    dim_parts = [f"'TODO_Table'[{col}]" for col in dims]
    measure_parts = [f'"{col}", [{safe_name(col)}]' for col in measures]

    all_parts = dim_parts + measure_parts
    body = ",\n    ".join(all_parts)

    if not all_parts:
        return f"EVALUATE ROW(\"TODO\", \"Fill in DAX query for {report_name}\")"

    return f"EVALUATE\nSUMMARIZECOLUMNS(\n    {body}\n)"


def make_tablix_xml(report_name: str, columns: list, dataset_name: str) -> str:
    """Generate a complete Tablix (table) element for the report body."""
    col_count = len(columns)
    if col_count == 0:
        return ""
    col_width = max(0.75, min(2.0, 7.5 / col_count))

    header_cells = []
    data_cells = []
    col_defs = []
    tablix_members = []

    for col in columns:
        fn = safe_name(col)
        col_defs.append(f"""          <TablixColumn>
            <Width>{col_width:.4f}in</Width>
          </TablixColumn>""")

        header_cells.append(f"""              <TablixCell>
                <CellContents>
                  <Textbox Name="Hdr_{fn}">
                    <CanGrow>true</CanGrow>
                    <KeepTogether>true</KeepTogether>
                    <Paragraphs>
                      <Paragraph>
                        <TextRuns>
                          <TextRun>
                            <Value>{xe(col)}</Value>
                            <Style><FontWeight>Bold</FontWeight></Style>
                          </TextRun>
                        </TextRuns>
                        <Style><TextAlign>Center</TextAlign></Style>
                      </Paragraph>
                    </Paragraphs>
                    <Style>
                      <Border><Color>LightGrey</Color><Style>Solid</Style></Border>
                      <PaddingLeft>2pt</PaddingLeft><PaddingRight>2pt</PaddingRight>
                      <PaddingTop>2pt</PaddingTop><PaddingBottom>2pt</PaddingBottom>
                    </Style>
                  </Textbox>
                </CellContents>
              </TablixCell>""")

        data_cells.append(f"""              <TablixCell>
                <CellContents>
                  <Textbox Name="{fn}">
                    <CanGrow>true</CanGrow>
                    <KeepTogether>true</KeepTogether>
                    <Paragraphs>
                      <Paragraph>
                        <TextRuns>
                          <TextRun>
                            <Value>=Fields!{fn}.Value</Value>
                            <Style/>
                          </TextRun>
                        </TextRuns>
                        <Style/>
                      </Paragraph>
                    </Paragraphs>
                    <Style>
                      <Border><Color>LightGrey</Color><Style>Solid</Style></Border>
                      <PaddingLeft>2pt</PaddingLeft><PaddingRight>2pt</PaddingRight>
                      <PaddingTop>2pt</PaddingTop><PaddingBottom>2pt</PaddingBottom>
                    </Style>
                  </Textbox>
                </CellContents>
              </TablixCell>""")

        tablix_members.append("            <TablixMember/>")

    hdr_row = "\n".join(header_cells)
    data_row = "\n".join(data_cells)
    col_defs_xml = "\n".join(col_defs)
    members_xml = "\n".join(tablix_members)
    ds_safe = safe_name(dataset_name)

    return f"""      <Tablix Name="MainTable">
        <DataSetName>{ds_safe}</DataSetName>
        <Top>0.1in</Top>
        <Left>0.1in</Left>
        <Height>6in</Height>
        <TablixBody>
          <TablixColumns>
{col_defs_xml}
          </TablixColumns>
          <TablixRows>
            <TablixRow>
              <Height>0.25in</Height>
              <TablixCells>
{hdr_row}
              </TablixCells>
            </TablixRow>
            <TablixRow>
              <Height>0.25in</Height>
              <TablixCells>
{data_row}
              </TablixCells>
            </TablixRow>
          </TablixRows>
        </TablixBody>
        <TablixColumnHierarchy>
          <TablixMembers>
{members_xml}
          </TablixMembers>
        </TablixColumnHierarchy>
        <TablixRowHierarchy>
          <TablixMembers>
            <TablixMember>
              <KeepWithGroup>After</KeepWithGroup>
            </TablixMember>
            <TablixMember>
              <Group Name="{ds_safe}_Detail"/>
            </TablixMember>
          </TablixMembers>
        </TablixRowHierarchy>
      </Tablix>"""


def _build_param_grid(user_params: list) -> str:
    """Build <ReportParametersLayout> grid XML.
    ExecDateTime is always col=0 row=0 (hidden).
    User params follow starting at col=1.
    """
    cells = [
        "        <CellDefinition>\n"
        "          <ColumnIndex>0</ColumnIndex>\n"
        "          <RowIndex>0</RowIndex>\n"
        "          <ParameterName>ExecDateTime</ParameterName>\n"
        "        </CellDefinition>"
    ]
    col = 1
    for p in user_params:
        if "label" not in p:
            continue
        pname = safe_name(p["label"])
        row = col // 4
        c = col % 4
        cells.append(
            f"        <CellDefinition>\n"
            f"          <ColumnIndex>{c}</ColumnIndex>\n"
            f"          <RowIndex>{row}</RowIndex>\n"
            f"          <ParameterName>{pname}</ParameterName>\n"
            f"        </CellDefinition>"
        )
        col += 1

    n_rows = max(1, (col + 3) // 4)
    cells_xml = "\n".join(cells)
    return f"""  <ReportParametersLayout>
    <GridLayoutDefinition>
      <NumberOfColumns>4</NumberOfColumns>
      <NumberOfRows>{n_rows}</NumberOfRows>
      <CellDefinitions>
{cells_xml}
      </CellDefinitions>
    </GridLayoutDefinition>
  </ReportParametersLayout>"""


def _date_range_xml(user_params: list) -> str:
    """Return the Date Range textbox XML for the page header.
    Uses StartDate/EndDate if present; otherwise shows a placeholder."""
    has_start = any(p.get("label", "").lower() in ("start date", "startdate", "begin date") for p in user_params)
    has_end = any(p.get("label", "").lower() in ("end date", "enddate", "through date") for p in user_params)
    start_param = "StartDate" if has_start else None
    end_param = "EndDate" if has_end else None

    if start_param and end_param:
        date_runs = f"""                  <TextRun>
                    <Value>Date Range: </Value>
                    <Style />
                  </TextRun>
                  <TextRun>
                    <Value>=Parameters!{start_param}.Value</Value>
                    <Style><Format>MM/dd/yyyy</Format></Style>
                  </TextRun>
                  <TextRun>
                    <Value> - </Value>
                    <Style />
                  </TextRun>
                  <TextRun>
                    <Value>=Parameters!{end_param}.Value</Value>
                    <Style><Format>MM/dd/yyyy</Format></Style>
                  </TextRun>"""
    else:
        date_runs = """                  <TextRun>
                    <Value>Date Range: </Value>
                    <Style />
                  </TextRun>"""

    return f"""            <Textbox Name="DateRange">
              <CanGrow>true</CanGrow>
              <KeepTogether>true</KeepTogether>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
{date_runs}
                  </TextRuns>
                  <Style><TextAlign>Left</TextAlign></Style>
                </Paragraph>
              </Paragraphs>
              <Top>0.51042in</Top>
              <Left>1.01389in</Left>
              <Height>0.39521in</Height>
              <Width>4.6193in</Width>
              <ZIndex>2</ZIndex>
              <Style>
                <Border><Style>None</Style></Border>
                <PaddingLeft>2pt</PaddingLeft><PaddingRight>2pt</PaddingRight>
                <PaddingTop>2pt</PaddingTop><PaddingBottom>2pt</PaddingBottom>
              </Style>
            </Textbox>"""


def generate_rdl(report: dict) -> str:
    """Generate a complete .rdl XML document for a paginated report."""
    name = safe_comment(report["name"])
    summary = safe_comment(report.get("summary", ""))
    params = report.get("parameters", [])
    layout = report.get("layout", {})
    requirements = report.get("requirements", [])
    notes = safe_comment(report.get("notes", ""))
    datasource_type = report.get("datasource_type", "semantic_model")
    generated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    report_id = str(uuid.uuid4())

    # Load config (may be None if pbi.properties missing)
    c = _get_cfg()

    # Collect all columns from layout sections
    all_columns = []
    for section in layout.values():
        all_columns.extend(section.get("columns", []))
    seen = set()
    unique_columns = []
    for col in all_columns:
        key = safe_name(col)
        if key not in seen and key:
            seen.add(key)
            unique_columns.append(col)

    # Requirements as plain text (nested XML comments are illegal)
    req_lines = "\n".join(
        f"  - {r.get('id','')}: {safe_comment(r.get('text',''))}" for r in requirements
    )

    # ── User parameters (from FRD) ──────────────────────────────────────
    # QueryParameters (@param syntax) are only valid for ODBC/SQL data sources.
    # DAX queries on a Semantic Model do not support @param substitution — including
    # QueryParameters for a DAX dataset causes "parameter not referred in query".
    is_odbc = datasource_type in ("snowflake", "db2")
    user_rp_parts = []
    query_params_xml = ""
    qp_parts = []
    for p in params:
        if "label" in p:
            rp, qp = make_parameter_xml(p)
            user_rp_parts.append(rp)
            if is_odbc:
                qp_parts.append(qp)
    if qp_parts:
        query_params_xml = (
            "        <QueryParameters>\n"
            + "\n".join(qp_parts)
            + "\n        </QueryParameters>"
        )

    # ── ExecDateTime hidden parameter (always first) ────────────────────
    exec_dt_param = """    <ReportParameter Name="ExecDateTime">
      <DataType>String</DataType>
      <DefaultValue>
        <Values>
          <Value>=Code.GetCST()</Value>
        </Values>
      </DefaultValue>
      <Prompt>ReportParameter1</Prompt>
      <Hidden>true</Hidden>
      <cl:ComponentMetadata>
        <cl:HideUpdateNotifications>true</cl:HideUpdateNotifications>
      </cl:ComponentMetadata>
    </ReportParameter>"""

    all_rp_parts = [exec_dt_param] + user_rp_parts
    report_params_xml = (
        "  <ReportParameters>\n"
        + "\n".join(all_rp_parts)
        + "\n  </ReportParameters>"
    )

    # ── Parameter grid layout ───────────────────────────────────────────
    param_grid_xml = _build_param_grid(params)

    # ── DataSource & DataSet ────────────────────────────────────────────
    ds_safe = safe_name(name)
    if datasource_type == "semantic_model":
        semantic_model = guess_semantic_model(report)   # honours _spec_model
        # Use spec-confirmed values when present (set by spec_parser from the Data Source section)
        ds_name = (
            report.get("_spec_datasource_name")
            or (c.datasource_name(semantic_model) if c else f"MissouriD1V1_{semantic_model.replace(' ', '_')}")
        )
        connect_str = (
            report.get("_spec_connect_string")
            or (c.connect_string(semantic_model) if c else (
                f'Data Source=pbiazure://api.powerbi.com/;'
                f'Identity Provider="https://login.microsoftonline.com/organizations, '
                f'https://analysis.windows.net/powerbi/api, TODO_TENANT_ID";'
                f'Initial Catalog=sobe_wowvirtualserver-TODO_GUID;'
                f'Integrated Security=ClaimsToken'
            ))
        )
        workspace = c.workspace_name if c else "Missouri - D1V1"

        datasource_xml = f"""  <DataSources>
    <DataSource Name="{ds_name}">
      <rd:SecurityType>None</rd:SecurityType>
      <ConnectionProperties>
        <DataProvider>PBIDATASET</DataProvider>
        <ConnectString>{xe(connect_str)}</ConnectString>
      </ConnectionProperties>
      <rd:DataSourceID>{str(uuid.uuid4())}</rd:DataSourceID>
      <rd:PowerBIWorkspaceName>{xe(workspace)}</rd:PowerBIWorkspaceName>
      <rd:PowerBIDatasetName>{xe(semantic_model)}</rd:PowerBIDatasetName>
    </DataSource>
  </DataSources>"""

        dax_query = make_dax_query(name, unique_columns, ds_safe)
        fields_xml = "\n".join(
            f"""        <Field Name="{safe_name(col)}">
          <rd:TypeName>System.String</rd:TypeName>
          <DataField>TODO_Table[{xe(col)}]</DataField>
        </Field>"""
            for col in unique_columns
        )
        dataset_xml = f"""  <DataSets>
    <DataSet Name="{ds_safe}">
      <Query>
        <DataSourceName>{ds_name}</DataSourceName>
{query_params_xml}
        <CommandText>{xe(dax_query)}</CommandText>
      </Query>
      <Fields>
{fields_xml}
      </Fields>
    </DataSet>
  </DataSets>"""

    else:
        # ODBC / DB2 (BOADB) or Snowflake direct ODBC
        if datasource_type == "db2":
            db_name  = c.db2_source_name  if c else "BOADB"
            dsn_name = c.db2_dsn          if c else "MOS-Q1-BOADB"
        else:
            db_name  = c.sfodbc_source_name if c else "LPC_E2_SFODBC"
            dsn_name = c.sfodbc_dsn         if c else "MOS-PX-SFODBC"
        datasource_xml = f"""  <DataSources>
    <DataSource Name="{db_name}">
      <rd:SecurityType>DataBase</rd:SecurityType>
      <ConnectionProperties>
        <DataProvider>ODBC</DataProvider>
        <ConnectString>Dsn={dsn_name}</ConnectString>
        <Prompt>Specify a user name and password for data source {db_name}:</Prompt>
      </ConnectionProperties>
      <rd:DataSourceID>{str(uuid.uuid4())}</rd:DataSourceID>
    </DataSource>
  </DataSources>"""

        # ── SQL: spec-embedded > hand-authored file > auto-generated stub ──
        sql_text = report.get("_spec_sql") or _load_sql(report["name"])
        sql_source = "file"
        if sql_text is None:
            sql_source = "stub"
            select_cols = ",\n    ".join(
                f"-- TODO_schema.TODO_table.[{col}] AS \"{col}\"" for col in unique_columns
            )
            where_hints = [
                r["text"] for r in requirements
                if any(kw in r["text"].lower() for kw in
                       ["shall include", "shall exclude", "having", "status of", "equal to"])
            ]
            where_block = (
                "WHERE\n  " + "\n  -- AND ".join(f"/* {h} */" for h in where_hints)
                if where_hints else ""
            )
            sql_hint = re.sub(r"[^\w\s\-]", "", report["name"]).strip().replace(" ", "_")
            sql_text = (
                f"-- AUTO-GENERATED STUB: replace with actual SQL\n"
                f"-- Or place hand-authored SQL in: sql/{sql_hint}.sql\n"
                f"SELECT\n    {select_cols}\nFROM\n    TODO_schema.TODO_table\n{where_block}"
            )

        fields_xml = "\n".join(
            f"""        <Field Name="{safe_name(col)}">
          <rd:TypeName>System.String</rd:TypeName>
          <DataField>{xe(col)}</DataField>
        </Field>"""
            for col in unique_columns
        )
        dataset_xml = f"""  <DataSets>
    <DataSet Name="{ds_safe}">
      <Query>
        <DataSourceName>{db_name}</DataSourceName>
{query_params_xml}
        <!-- sql_source: {sql_source} -->
        <CommandText>{xe(sql_text)}</CommandText>
      </Query>
      <Fields>
{fields_xml}
      </Fields>
    </DataSet>
  </DataSets>"""

    # ── Body tablix ────────────────────────────────────────────────────
    tablix_xml = make_tablix_xml(name, unique_columns, name)

    # Estimate body height (rows ~ columns * 3, capped at 250)
    est_rows = max(20, len(unique_columns) * 3)
    body_height = round(min(est_rows, 250) * 0.25 + 1.0, 2)

    # ── Embedded logo ──────────────────────────────────────────────────
    logo_b64 = c.logo_b64 if c else ""
    if logo_b64:
        embedded_images_xml = f"""  <EmbeddedImages>
    <EmbeddedImage Name="molotterylogov">
      <MIMEType>image/png</MIMEType>
      <ImageData>{logo_b64}</ImageData>
    </EmbeddedImage>
  </EmbeddedImages>"""
        logo_item_xml = """            <Image Name="Logo">
              <Source>Embedded</Source>
              <Value>molotterylogov</Value>
              <Sizing>FitProportional</Sizing>
              <Left>0.01389in</Left>
              <Height>0.90563in</Height>
              <Width>1in</Width>
              <ZIndex>3</ZIndex>
              <Style><Border><Style>None</Style></Border></Style>
            </Image>"""
    else:
        embedded_images_xml = ""
        logo_item_xml = ""

    # ── Date range row in header (shows StartDate/EndDate if present) ──
    date_range_item_xml = _date_range_xml(params)

    # ── Page dimensions from config ────────────────────────────────────
    page_w = c.page_width if c else "11in"
    page_h = c.page_height if c else "8.5in"
    margin = c.margin if c else "0.2in"
    hdr_h = c.header_height if c else "0.90563in"
    ftr_h = c.footer_height if c else "0.42486in"

    rdl = f"""<?xml version="1.0" encoding="utf-8"?>
<!--
  ============================================================
  Report    : {name}
  Folder    : {safe_comment(report.get('folder', ''))} / {safe_comment(report.get('target_folder', ''))}
  Format    : Paginated (.rdl)
  DataSource: {datasource_type}
  Generated : {generated_at}
  Summary   : {summary}
  Notes     : {notes}
  Legacy    : {safe_comment(report.get('legacy_reports', ''))}

  REQUIREMENTS:
{req_lines}
  ============================================================
-->
<Report MustUnderstand="df"
  xmlns="{RDL_NS}"
  xmlns:rd="{RDL_RD}"
  xmlns:cl="{RDL_CL}"
  xmlns:df="{RDL_DF}"
  xmlns:am="{RDL_AM}">

  <rd:ReportUnitType>Inch</rd:ReportUnitType>
  <rd:ReportID>{report_id}</rd:ReportID>
  <am:AuthoringMetadata>
    <am:CreatedBy><am:Name>FRD-AutoGenerator</am:Name><am:Version>2.0.0</am:Version></am:CreatedBy>
    <am:LastModifiedTimestamp>{generated_at}</am:LastModifiedTimestamp>
  </am:AuthoringMetadata>
  <df:DefaultFontFamily>Segoe UI</df:DefaultFontFamily>
  <AutoRefresh>0</AutoRefresh>

{datasource_xml}

{dataset_xml}

  <ReportSections>
    <ReportSection>
      <Body>
        <Height>{body_height}in</Height>
        <ReportItems>

{tablix_xml}

        </ReportItems>
        <Style>
          <Border><Style>None</Style></Border>
        </Style>
      </Body>
      <Width>10.5in</Width>
      <Page>
        <PageHeader>
          <Height>{hdr_h}</Height>
          <PrintOnFirstPage>true</PrintOnFirstPage>
          <PrintOnLastPage>true</PrintOnLastPage>
          <ReportItems>
            <Textbox Name="ReportTitle">
              <CanGrow>true</CanGrow>
              <KeepTogether>true</KeepTogether>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
                    <TextRun>
                      <Value>{xe(name)}</Value>
                      <Style>
                        <FontStyle>Normal</FontStyle>
                        <FontFamily>{c.title_font if c else "Segoe UI Light"}</FontFamily>
                        <FontSize>{c.title_font_size if c else "14pt"}</FontSize>
                        <FontWeight>Bold</FontWeight>
                        <TextDecoration>None</TextDecoration>
                      </Style>
                    </TextRun>
                  </TextRuns>
                  <Style />
                </Paragraph>
              </Paragraphs>
              <Left>1.01389in</Left>
              <Height>0.51042in</Height>
              <Width>4.6193in</Width>
              <Style>
                <Border><Style>None</Style></Border>
                <PaddingLeft>2pt</PaddingLeft><PaddingRight>2pt</PaddingRight>
                <PaddingTop>2pt</PaddingTop><PaddingBottom>2pt</PaddingBottom>
              </Style>
            </Textbox>
            <Textbox Name="ExecutionTime">
              <CanGrow>true</CanGrow>
              <KeepTogether>true</KeepTogether>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
                    <TextRun>
                      <Value>Run Datetime: </Value>
                      <Style />
                    </TextRun>
                  </TextRuns>
                  <Style><TextAlign>Left</TextAlign></Style>
                </Paragraph>
                <Paragraph>
                  <TextRuns>
                    <TextRun>
                      <Value>=Parameters!ExecDateTime.Value</Value>
                      <Style />
                    </TextRun>
                  </TextRuns>
                  <Style><TextAlign>Left</TextAlign></Style>
                </Paragraph>
              </Paragraphs>
              <Left>6.97916in</Left>
              <Height>0.51042in</Height>
              <Width>2.54167in</Width>
              <ZIndex>1</ZIndex>
              <Style>
                <Border><Style>None</Style></Border>
                <PaddingLeft>2pt</PaddingLeft><PaddingRight>2pt</PaddingRight>
                <PaddingTop>2pt</PaddingTop><PaddingBottom>2pt</PaddingBottom>
              </Style>
            </Textbox>
{date_range_item_xml}
{logo_item_xml}
          </ReportItems>
          <Style>
            <Border><Style>None</Style></Border>
          </Style>
        </PageHeader>
        <PageFooter>
          <Height>{ftr_h}</Height>
          <PrintOnFirstPage>true</PrintOnFirstPage>
          <PrintOnLastPage>true</PrintOnLastPage>
          <ReportItems>
            <Textbox Name="FooterReportName">
              <CanGrow>true</CanGrow>
              <KeepTogether>true</KeepTogether>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
                    <TextRun>
                      <Value>=Globals!ReportName</Value>
                      <Style />
                    </TextRun>
                  </TextRuns>
                  <Style />
                </Paragraph>
              </Paragraphs>
              <Top>0.06944in</Top>
              <Height>0.25in</Height>
              <Width>3.40625in</Width>
              <Style>
                <Border><Style>None</Style></Border>
                <PaddingLeft>2pt</PaddingLeft><PaddingRight>2pt</PaddingRight>
                <PaddingTop>2pt</PaddingTop><PaddingBottom>2pt</PaddingBottom>
              </Style>
            </Textbox>
            <Textbox Name="FooterPageNumber">
              <CanGrow>true</CanGrow>
              <KeepTogether>true</KeepTogether>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
                    <TextRun><Value>Page </Value><Style /></TextRun>
                    <TextRun><Value>=Globals!OverallPageNumber</Value><Style /></TextRun>
                    <TextRun><Value> of </Value><Style /></TextRun>
                    <TextRun><Value>=Globals!OverallTotalPages</Value><Style /></TextRun>
                  </TextRuns>
                  <Style><TextAlign>Left</TextAlign></Style>
                </Paragraph>
              </Paragraphs>
              <Top>0.06944in</Top>
              <Left>8.34375in</Left>
              <Height>0.25in</Height>
              <Width>1.17708in</Width>
              <ZIndex>1</ZIndex>
              <Style>
                <Border><Style>None</Style></Border>
                <PaddingLeft>2pt</PaddingLeft><PaddingRight>2pt</PaddingRight>
                <PaddingTop>2pt</PaddingTop><PaddingBottom>2pt</PaddingBottom>
              </Style>
            </Textbox>
          </ReportItems>
          <Style>
            <Border><Style>None</Style></Border>
          </Style>
        </PageFooter>
        <PageHeight>{page_h}</PageHeight>
        <PageWidth>{page_w}</PageWidth>
        <LeftMargin>{margin}</LeftMargin>
        <RightMargin>{margin}</RightMargin>
        <TopMargin>{margin}</TopMargin>
        <BottomMargin>{margin}</BottomMargin>
        <Style />
      </Page>
    </ReportSection>
  </ReportSections>

{report_params_xml}

{param_grid_xml}

  <Code>Public Function GetCST() As DateTime
    Return TimeZoneInfo.ConvertTimeFromUtc(DateTime.UtcNow, TimeZoneInfo.FindSystemTimeZoneById("{c.timezone if c else "Central Standard Time"}"))
End Function
</Code>

{embedded_images_xml}

  <Language>en-US</Language>

</Report>
"""
    return rdl


def generate_all_rdl(parsed_frd: dict, output_dir: str) -> list:
    """Generate RDL files for all paginated reports in the parsed FRD."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = []

    for report in parsed_frd["reports"]:
        if report["report_format"] != "Paginated":
            continue
        folder = safe_name(report.get("target_folder") or report["folder"])
        subfolder = out / folder
        subfolder.mkdir(exist_ok=True)

        safe_rpt_name = re.sub(r"[^\w\s\-]", "", report["name"]).strip().replace(" ", "_")
        filepath = subfolder / f"{safe_rpt_name}.rdl"
        filepath.write_text(generate_rdl(report), encoding="utf-8")
        generated.append(str(filepath))

    return generated


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Generate RDL files from parsed FRD JSON")
    ap.add_argument("frd_json", help="Parsed FRD JSON file (output of frd_parser.py)")
    ap.add_argument("-o", "--output", default="output/rdl")
    ap.add_argument("--report", help="Filter to a specific report name (partial match)")
    args = ap.parse_args()

    with open(args.frd_json, encoding="utf-8") as f:
        frd = json.load(f)

    if args.report:
        frd["reports"] = [r for r in frd["reports"] if args.report.lower() in r["name"].lower()]

    files = generate_all_rdl(frd, args.output)
    print(f"Generated {len(files)} .rdl files → {args.output}")
    for f in files[:10]:
        print(f"  {f}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")
