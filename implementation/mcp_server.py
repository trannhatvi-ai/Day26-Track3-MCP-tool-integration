from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from fastmcp.exceptions import ResourceError, ToolError

try:
    from .db import SQLiteAdapter, ValidationError
    from .init_db import DEFAULT_DB_PATH, create_database
except ImportError:
    from db import SQLiteAdapter, ValidationError
    from init_db import DEFAULT_DB_PATH, create_database


mcp = FastMCP("SQLite Lab MCP Server")
_adapter: SQLiteAdapter | None = None
_adapter_path: Path | None = None


def get_database_path() -> Path:
    return Path(os.environ.get("SQLITE_LAB_DB", DEFAULT_DB_PATH)).resolve()


def get_adapter() -> SQLiteAdapter:
    global _adapter, _adapter_path

    db_path = get_database_path()
    if _adapter is None or _adapter_path != db_path:
        if not db_path.exists():
            create_database(db_path)
        _adapter = SQLiteAdapter(db_path)
        _adapter_path = db_path
    return _adapter


def reset_adapter_for_tests() -> None:
    global _adapter, _adapter_path
    _adapter = None
    _adapter_path = None


def _raise_tool_error(exc: ValidationError) -> None:
    raise ToolError(str(exc)) from exc


@mcp.tool(name="search")
def search(
    table: str,
    filters: dict[str, Any] | list[dict[str, Any]] | None = None,
    columns: list[str] | None = None,
    limit: int = 20,
    offset: int = 0,
    order_by: str | None = None,
    descending: bool = False,
) -> dict[str, Any]:
    """Search rows in a validated table with filters, ordering, and pagination."""
    try:
        return get_adapter().search(
            table=table,
            columns=columns,
            filters=filters,
            limit=limit,
            offset=offset,
            order_by=order_by,
            descending=descending,
        )
    except ValidationError as exc:
        _raise_tool_error(exc)


@mcp.tool(name="insert")
def insert(table: str, values: dict[str, Any]) -> dict[str, Any]:
    """Insert a row into a validated table and return the persisted payload."""
    try:
        return get_adapter().insert(table=table, values=values)
    except ValidationError as exc:
        _raise_tool_error(exc)


@mcp.tool(name="aggregate")
def aggregate(
    table: str,
    metric: str,
    column: str | None = None,
    filters: dict[str, Any] | list[dict[str, Any]] | None = None,
    group_by: str | list[str] | None = None,
) -> dict[str, Any]:
    """Run count, avg, sum, min, or max against a validated table."""
    try:
        return get_adapter().aggregate(
            table=table,
            metric=metric,
            column=column,
            filters=filters,
            group_by=group_by,
        )
    except ValidationError as exc:
        _raise_tool_error(exc)


@mcp.resource("schema://database")
def database_schema() -> str:
    """Return the full database schema as formatted JSON text."""
    return json.dumps(get_adapter().describe_database(), indent=2)


@mcp.resource("schema://table/{table_name}")
def table_schema(table_name: str) -> str:
    """Return one table schema as formatted JSON text."""
    try:
        payload = get_adapter().get_table_schema(table_name)
    except ValidationError as exc:
        raise ResourceError(str(exc)) from exc
    return json.dumps(payload, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SQLite lab FastMCP server.")
    parser.add_argument(
        "--transport",
        choices=("stdio", "http", "sse"),
        default=os.environ.get("MCP_TRANSPORT", "stdio"),
        help="MCP transport. Use stdio for clients/Inspector or http/sse for localhost demos.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Host for http/sse transports.")
    parser.add_argument("--port", type=int, default=8000, help="Port for http/sse transports.")
    parser.add_argument("--path", default="/mcp", help="HTTP MCP path.")
    args = parser.parse_args()

    get_adapter()
    if args.transport == "stdio":
        mcp.run()
    else:
        mcp.run(transport=args.transport, host=args.host, port=args.port, path=args.path)


if __name__ == "__main__":
    main()

