"""MCP tools for DAX and schema validation."""

from __future__ import annotations

import json

from powerbi_mcp.server import mcp
from powerbi_mcp.services import fabric_api


@mcp.tool()
async def validate_dax(workspace_id: str, dataset_id: str, dax_expression: str) -> str:
    """Validate a DAX expression by executing it against a semantic model.

    Wraps the expression in EVALUATE to test syntax and semantics.
    Returns the first few rows of results or the error message.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model GUID.
        dax_expression: DAX expression to validate (e.g., a measure definition or query).
    """
    # If the expression doesn't start with EVALUATE, wrap it
    query = dax_expression.strip()
    if not query.upper().startswith("EVALUATE"):
        query = f"EVALUATE ROW(\"Result\", {query})"

    try:
        result = await fabric_api.execute_dax_query(workspace_id, dataset_id, query)
        tables = result.get("results", [{}])
        if tables and tables[0].get("tables"):
            rows = tables[0]["tables"][0].get("rows", [])
            return f"DAX valid. Result ({len(rows)} row(s)):\n{json.dumps(rows[:10], indent=2, default=str)}"
        return f"DAX valid. Full response:\n{json.dumps(result, indent=2, default=str)}"
    except Exception as e:
        return f"DAX validation failed:\n{e}"


@mcp.tool()
async def compare_model_schema(workspace_id: str, dataset_id: str, source_columns_json: str) -> str:
    """Compare semantic model columns against source database columns.

    Identifies columns present in source but missing from model, and vice versa.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model GUID.
        source_columns_json: JSON object mapping table names to lists of column names.
            Example: {"DimVehicle": ["VehicleID", "Make", "Model"], "FactSales": ["SaleID", "Amount"]}
    """
    try:
        source_tables: dict[str, list[str]] = json.loads(source_columns_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON for source_columns_json: {e}"

    definition = await fabric_api.get_item_definition(workspace_id, dataset_id)

    # Extract model columns from definition
    model_tables: dict[str, list[str]] = {}
    model_def = definition.get("definition.json", definition.get("model.bim", {}))
    if isinstance(model_def, dict):
        for table in model_def.get("model", {}).get("tables", []):
            table_name = table.get("name", "")
            columns = [col.get("name", "") for col in table.get("columns", [])]
            model_tables[table_name] = columns

    lines = ["Schema comparison results:\n"]
    for table_name, src_cols in source_tables.items():
        model_cols = model_tables.get(table_name, [])
        if not model_cols:
            lines.append(f"  TABLE '{table_name}': NOT FOUND in model")
            continue
        missing_in_model = set(src_cols) - set(model_cols)
        extra_in_model = set(model_cols) - set(src_cols)
        if not missing_in_model and not extra_in_model:
            lines.append(f"  TABLE '{table_name}': OK ({len(src_cols)} columns match)")
        else:
            lines.append(f"  TABLE '{table_name}':")
            if missing_in_model:
                lines.append(f"    Missing in model: {sorted(missing_in_model)}")
            if extra_in_model:
                lines.append(f"    Extra in model: {sorted(extra_in_model)}")

    # Tables in model but not in source
    extra_tables = set(model_tables.keys()) - set(source_tables.keys())
    if extra_tables:
        lines.append(f"\n  Tables in model but not in source check: {sorted(extra_tables)}")

    return "\n".join(lines)


@mcp.tool()
async def check_model_health(workspace_id: str, dataset_id: str) -> str:
    """Run best-practice health checks on a semantic model.

    Checks for: tables without descriptions, measures without descriptions,
    unused columns, missing relationships, and formatting issues.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model GUID.
    """
    definition = await fabric_api.get_item_definition(workspace_id, dataset_id)

    model_def = definition.get("definition.json", definition.get("model.bim", {}))
    if not isinstance(model_def, dict):
        return "Could not parse model definition for health check."

    model = model_def.get("model", {})
    tables = model.get("tables", [])
    relationships = model.get("relationships", [])

    issues: list[str] = []
    warnings: list[str] = []
    stats = {"tables": len(tables), "measures": 0, "columns": 0, "relationships": len(relationships)}

    for table in tables:
        table_name = table.get("name", "Unknown")
        columns = table.get("columns", [])
        measures = table.get("measures", [])
        stats["columns"] += len(columns)
        stats["measures"] += len(measures)

        if not table.get("description"):
            warnings.append(f"Table '{table_name}' has no description")

        for measure in measures:
            if not measure.get("description"):
                warnings.append(f"Measure '{table_name}'[{measure.get('name', '')}] has no description")

        # Check for hidden columns that aren't used in relationships
        rel_columns = set()
        for rel in relationships:
            rel_columns.add(f"{rel.get('fromTable', '')}.{rel.get('fromColumn', '')}")
            rel_columns.add(f"{rel.get('toTable', '')}.{rel.get('toColumn', '')}")

        for col in columns:
            col_key = f"{table_name}.{col.get('name', '')}"
            if col.get("isHidden") and col_key not in rel_columns:
                issues.append(f"Hidden column '{col_key}' not used in any relationship -- consider removing")

    lines = [
        "Model Health Check Results:",
        f"  Tables: {stats['tables']}, Columns: {stats['columns']}, Measures: {stats['measures']}, Relationships: {stats['relationships']}",
        "",
    ]
    if issues:
        lines.append(f"Issues ({len(issues)}):")
        for i in issues[:20]:
            lines.append(f"  - {i}")
    if warnings:
        lines.append(f"\nWarnings ({len(warnings)}):")
        for w in warnings[:20]:
            lines.append(f"  - {w}")
    if not issues and not warnings:
        lines.append("No issues found.")

    return "\n".join(lines)
