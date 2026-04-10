"""
rdl_generator.py
Generates .rdl (Report Definition Language) XML for paginated Power BI reports.

Improvements over reference implementation:
- Correct RDL structure: uses <ReportSections><ReportSection> wrapper (2016 schema)
- Correct namespaces matching real Power BI Report Builder output
- Semantic model datasource uses PBIDATASET provider + DAX EVALUATE query
- ODBC/DB2 datasource uses ODBC provider + SQL query
- Field DataField format: 'TableName[ColumnName]' for dimensions (semantic model)
- Proper parameter linkage via <QueryParameters>
- Inch-based measurements matching real templates
- Segoe UI font throughout
"""

import json
import re
import textwrap
import uuid
from pathlib import Path
from datetime import datetime

# RDL namespaces matching real Power BI Report Builder output
RDL_NS = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition"
RDL_RD = "http://schemas.microsoft.com/SQLServer/reporting/reportdesigner"
RDL_DF = "http://schemas.microsoft.com/sqlserver/reporting/2016/01/reportdefinition/defaultfontfamily"
RDL_AM = "http://schemas.microsoft.com/sqlserver/reporting/authoringmetadata"

# Default semantic model workspace — developer updates this
DEFAULT_WORKSPACE = "Missouri - D1V1"
DEFAULT_DATASET = "MO_Sales"  # TODO: match per report


def safe_name(text: str) -> str:
    """Convert arbitrary text to a safe XML/field identifier."""
    return re.sub(r"\W+", "_", text).strip("_")


def guess_semantic_model(report: dict) -> str:
    """
    Heuristically pick the most likely MO_* semantic model for a report.
    Returns just the dataset name (e.g. 'MO_Sales').
    """
    name_lower = (report.get("name", "") + " " + report.get("summary", "")).lower()
    model_hints = {
        "MO_Sales": ["sales", "retailer", "keno", "draw", "wager", "ticket"],
        "MO_Inventory": ["inventory", "pack", "activated", "aging", "bin"],
        "MO_Payments": ["payment", "check", "1042", "tax", "claim", "winner"],
        "MO_Promotions": ["promotion", "promo", "cashless"],
        "MO_Invoice": ["invoice", "brightstar"],
        "MO_DrawData": ["draw", "jackpot", "winning number"],
        "MO_WinnerData": ["winner", "prize", "claim"],
        "MO_LVMSales": ["lvm", "vending"],
        "MO_LVMTransactional": ["transaction", "lvm"],
        "MO_IntervalSales": ["interval", "hourly", "weekly"],
        "MO_CoreTables": ["retailer list", "chain", "district", "device", "terminal"],
    }
    for model, keywords in model_hints.items():
        if any(kw in name_lower for kw in keywords):
            return model
    return DEFAULT_DATASET


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
        <Values><Value>{dval}</Value></Values>
      </DefaultValue>"""

    report_param = f"""    <ReportParameter Name="{name}">
      <DataType>String</DataType>
      <Nullable>{nullable}</Nullable>
      {multi_xml}
      <Prompt>{label}</Prompt>{default}
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
                            <Value>{col}</Value>
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
        <Top>1.5in</Top>
        <Left>0.5in</Left>
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


def generate_rdl(report: dict) -> str:
    """Generate a complete .rdl XML document for a paginated report."""
    name = report["name"]
    summary = report.get("summary", "")
    params = report.get("parameters", [])
    layout = report.get("layout", {})
    requirements = report.get("requirements", [])
    notes = report.get("notes", "")
    datasource_type = report.get("datasource_type", "semantic_model")
    generated_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    report_id = str(uuid.uuid4())

    # Collect all columns from layout sections
    all_columns = []
    for section in layout.values():
        all_columns.extend(section.get("columns", []))
    seen = set()
    unique_columns = []
    for c in all_columns:
        key = safe_name(c)
        if key not in seen and key:
            seen.add(key)
            unique_columns.append(c)

    # Requirements as XML comments
    req_lines = "\n".join(
        f"  <!-- {r.get('id','')}: {r.get('text','')} -->" for r in requirements
    )

    # Parameters
    report_params_xml = ""
    query_params_xml = ""
    if params:
        rp_parts = []
        qp_parts = []
        for p in params:
            if "label" in p:
                rp, qp = make_parameter_xml(p)
                rp_parts.append(rp)
                qp_parts.append(qp)
        if rp_parts:
            report_params_xml = (
                "  <ReportParameters>\n"
                + "\n".join(rp_parts)
                + "\n  </ReportParameters>"
            )
            query_params_xml = (
                "        <QueryParameters>\n"
                + "\n".join(qp_parts)
                + "\n        </QueryParameters>"
            )

    # Dataset & DataSource
    ds_safe = safe_name(name)
    if datasource_type == "semantic_model":
        semantic_model = guess_semantic_model(report)
        datasource_xml = f"""  <DataSources>
    <DataSource Name="{safe_name(semantic_model)}">
      <rd:SecurityType>None</rd:SecurityType>
      <ConnectionProperties>
        <DataProvider>PBIDATASET</DataProvider>
        <!-- TODO: Update ConnectString with your Fabric workspace/dataset GUID -->
        <ConnectString>Data Source=pbiazure://api.powerbi.com/;Identity Provider="https://login.microsoftonline.com/organizations, https://analysis.windows.net/powerbi/api, TODO_TENANT_ID";Initial Catalog=sobe_wowvirtualserver-TODO_DATASET_GUID;Integrated Security=ClaimsToken</ConnectString>
      </ConnectionProperties>
      <rd:DataSourceID>{str(uuid.uuid4())}</rd:DataSourceID>
      <rd:PowerBIWorkspaceName>{DEFAULT_WORKSPACE}</rd:PowerBIWorkspaceName>
      <rd:PowerBIDatasetName>{semantic_model}</rd:PowerBIDatasetName>
    </DataSource>
  </DataSources>"""

        dax_query = make_dax_query(name, unique_columns, ds_safe)
        fields_xml = "\n".join(
            f"""        <Field Name="{safe_name(c)}">
          <rd:TypeName>System.String</rd:TypeName>
          <DataField>TODO_Table[{c}]</DataField>
        </Field>"""
            for c in unique_columns
        )
        dataset_xml = f"""  <DataSets>
    <DataSet Name="{ds_safe}">
      <Query>
        <DataSourceName>{safe_name(semantic_model)}</DataSourceName>
{query_params_xml}
        <CommandText>{dax_query}</CommandText>
      </Query>
      <Fields>
{fields_xml}
      </Fields>
    </DataSet>
  </DataSets>"""

    else:
        # ODBC / DB2 (BOADB) or Snowflake
        db_name = "BOADB" if datasource_type == "db2" else "SNOWFLAKE"
        dsn_name = "MOS-Q1-BOADB" if datasource_type == "db2" else "MOS-Q1-SNOWFLAKE"
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

        select_cols = ",\n    ".join(f"-- TODO_schema.TODO_table.[{c}] AS \"{c}\"" for c in unique_columns)
        where_hints = [
            r["text"] for r in requirements
            if any(kw in r["text"].lower() for kw in ["shall include", "shall exclude", "having", "status of", "equal to"])
        ]
        where_block = ""
        if where_hints:
            where_block = "WHERE\n  " + "\n  -- AND ".join(f"/* {h} */" for h in where_hints)
        fields_xml = "\n".join(
            f"""        <Field Name="{safe_name(c)}">
          <rd:TypeName>System.String</rd:TypeName>
          <DataField>{c}</DataField>
        </Field>"""
            for c in unique_columns
        )
        dataset_xml = f"""  <DataSets>
    <DataSet Name="{ds_safe}">
      <Query>
        <DataSourceName>{db_name}</DataSourceName>
{query_params_xml}
        <CommandText>
-- AUTO-GENERATED STUB: replace with actual SQL
SELECT
    {select_cols}
FROM
    TODO_schema.TODO_table
{where_block}
        </CommandText>
      </Query>
      <Fields>
{fields_xml}
      </Fields>
    </DataSet>
  </DataSets>"""

    # Report body tablix
    tablix_xml = make_tablix_xml(name, unique_columns, name)

    # Multi-section tables (one tablix per layout section if multiple sections)
    section_tablixes = []
    if len(layout) > 1:
        y_offset = 1.5
        for sec_name, sec_data in layout.items():
            cols = sec_data.get("columns", [])
            if not cols:
                continue
            safe_sec = safe_name(sec_name)[:20]
            col_w = max(0.75, min(2.0, 7.5 / len(cols)))
            section_tablixes.append(f"      <!-- Section: {sec_name} -->")
        # Use the combined tablix for now (developer can split later)

    rdl = f"""<?xml version="1.0" encoding="utf-8"?>
<!--
  ============================================================
  Report   : {name}
  Folder   : {report.get('folder', '')} / {report.get('target_folder', '')}
  Format   : Paginated (.rdl)
  DataSource: {datasource_type}
  Generated: {generated_at}
  Summary  : {summary}
  Notes    : {notes}
  Legacy   : {report.get('legacy_reports', '')}

  REQUIREMENTS:
{req_lines}
  ============================================================
-->
<Report MustUnderstand="df"
  xmlns="{RDL_NS}"
  xmlns:rd="{RDL_RD}"
  xmlns:df="{RDL_DF}"
  xmlns:am="{RDL_AM}">

  <rd:ReportUnitType>Inch</rd:ReportUnitType>
  <rd:ReportID>{report_id}</rd:ReportID>
  <am:AuthoringMetadata>
    <am:CreatedBy><am:Name>FRD-AutoGenerator</am:Name><am:Version>1.0.0</am:Version></am:CreatedBy>
    <am:LastModifiedTimestamp>{generated_at}</am:LastModifiedTimestamp>
  </am:AuthoringMetadata>
  <df:DefaultFontFamily>Segoe UI</df:DefaultFontFamily>
  <AutoRefresh>0</AutoRefresh>

{datasource_xml}

{dataset_xml}

{report_params_xml}

  <ReportSections>
    <ReportSection>
      <Body>
        <ReportItems>

          <!-- Report Title -->
          <Textbox Name="ReportTitle">
            <CanGrow>true</CanGrow>
            <Top>0.1in</Top><Left>0.5in</Left>
            <Height>0.4in</Height><Width>9in</Width>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>{name}</Value>
                    <Style><FontSize>14pt</FontSize><FontWeight>Bold</FontWeight></Style>
                  </TextRun>
                </TextRuns>
              </Paragraph>
            </Paragraphs>
          </Textbox>

          <!-- Run Date -->
          <Textbox Name="RunDate">
            <CanGrow>true</CanGrow>
            <Top>0.1in</Top><Left>9in</Left>
            <Height>0.4in</Height><Width>2in</Width>
            <Paragraphs>
              <Paragraph>
                <TextRuns>
                  <TextRun>
                    <Value>=Format(Globals!ExecutionTime, "MM/dd/yyyy")</Value>
                    <Style><FontSize>9pt</FontSize></Style>
                  </TextRun>
                </TextRuns>
                <Style><TextAlign>Right</TextAlign></Style>
              </Paragraph>
            </Paragraphs>
          </Textbox>

{tablix_xml}

        </ReportItems>
        <Style/>
      </Body>
      <Page>
        <PageWidth>11in</PageWidth>
        <PageHeight>8.5in</PageHeight>
        <LeftMargin>0.5in</LeftMargin>
        <RightMargin>0.5in</RightMargin>
        <TopMargin>0.5in</TopMargin>
        <BottomMargin>0.5in</BottomMargin>
        <Style><BackgroundColor>White</BackgroundColor></Style>
        <PageHeader>
          <ReportItems>
            <Textbox Name="PageHdr_Title">
              <CanGrow>true</CanGrow>
              <Top>0.05in</Top><Left>0.1in</Left>
              <Height>0.3in</Height><Width>7in</Width>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
                    <TextRun>
                      <Value>=Globals!ReportName</Value>
                      <Style><FontSize>9pt</FontWeight></Style>
                    </TextRun>
                  </TextRuns>
                </Paragraph>
              </Paragraphs>
            </Textbox>
            <Textbox Name="PageHdr_Date">
              <CanGrow>true</CanGrow>
              <Top>0.05in</Top><Left>8in</Left>
              <Height>0.3in</Height><Width>2.5in</Width>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
                    <TextRun>
                      <Value>=Format(Globals!ExecutionTime, "MM/dd/yyyy HH:mm:ss")</Value>
                      <Style><FontSize>8pt</FontSize></Style>
                    </TextRun>
                  </TextRuns>
                  <Style><TextAlign>Right</TextAlign></Style>
                </Paragraph>
              </Paragraphs>
            </Textbox>
          </ReportItems>
          <PrintOnFirstPage>true</PrintOnFirstPage>
          <PrintOnLastPage>true</PrintOnLastPage>
        </PageHeader>
        <PageFooter>
          <ReportItems>
            <Textbox Name="PageFtr_Name">
              <CanGrow>true</CanGrow>
              <Top>0.05in</Top><Left>0.1in</Left>
              <Height>0.3in</Height><Width>7in</Width>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
                    <TextRun>
                      <Value>{name}</Value>
                      <Style><FontSize>8pt</FontSize></Style>
                    </TextRun>
                  </TextRuns>
                </Paragraph>
              </Paragraphs>
            </Textbox>
            <Textbox Name="PageFtr_Page">
              <CanGrow>true</CanGrow>
              <Top>0.05in</Top><Left>8.5in</Left>
              <Height>0.3in</Height><Width>2in</Width>
              <Paragraphs>
                <Paragraph>
                  <TextRuns>
                    <TextRun>
                      <Value>=Globals!PageNumber &amp; " of " &amp; Globals!TotalPages</Value>
                      <Style><FontSize>8pt</FontSize></Style>
                    </TextRun>
                  </TextRuns>
                  <Style><TextAlign>Right</TextAlign></Style>
                </Paragraph>
              </Paragraphs>
            </Textbox>
          </ReportItems>
          <PrintOnFirstPage>true</PrintOnFirstPage>
          <PrintOnLastPage>true</PrintOnLastPage>
        </PageFooter>
      </Page>
    </ReportSection>
  </ReportSections>

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

    with open(args.frd_json) as f:
        frd = json.load(f)

    if args.report:
        frd["reports"] = [r for r in frd["reports"] if args.report.lower() in r["name"].lower()]

    files = generate_all_rdl(frd, args.output)
    print(f"Generated {len(files)} .rdl files → {args.output}")
    for f in files[:10]:
        print(f"  {f}")
    if len(files) > 10:
        print(f"  ... and {len(files) - 10} more")
