from __future__ import annotations

import asyncio
import contextlib
import io
import json
import os
from pathlib import Path

from fastmcp import Client

try:
    from .init_db import DEFAULT_DB_PATH, create_database
    from .mcp_server import mcp, reset_adapter_for_tests
except ImportError:
    from init_db import DEFAULT_DB_PATH, create_database
    from mcp_server import mcp, reset_adapter_for_tests


async def verify() -> dict[str, object]:
    db_path = Path(os.environ.get("SQLITE_LAB_DB", DEFAULT_DB_PATH)).resolve()
    create_database(db_path)
    reset_adapter_for_tests()

    report: dict[str, object] = {"database": str(db_path)}
    async with Client(mcp) as client:
        tools = await client.list_tools()
        report["tools"] = sorted(tool.name for tool in tools)

        resources = await client.list_resources()
        report["resources"] = sorted(str(resource.uri) for resource in resources)

        templates = await client.list_resource_templates()
        report["resource_templates"] = sorted(
            str(template.uriTemplate) for template in templates
        )

        search_result = await client.call_tool(
            "search",
            {
                "table": "students",
                "filters": {"cohort": "A1"},
                "order_by": "score",
                "descending": True,
                "limit": 2,
            },
        )
        report["search"] = search_result.data

        insert_result = await client.call_tool(
            "insert",
            {
                "table": "students",
                "values": {
                    "name": "Demo Student",
                    "cohort": "A4",
                    "email": "demo.student@example.com",
                    "score": 89.0,
                },
            },
        )
        report["insert"] = insert_result.data

        aggregate_result = await client.call_tool(
            "aggregate",
            {"table": "students", "metric": "avg", "column": "score", "group_by": "cohort"},
        )
        report["aggregate"] = aggregate_result.data

        schema_text = await client.read_resource("schema://database")
        report["schema_tables"] = sorted(json.loads(schema_text[0].text)["tables"].keys())

        with contextlib.redirect_stderr(io.StringIO()):
            try:
                await client.call_tool("search", {"table": "missing_table"})
            except Exception as exc:
                report["invalid_request_error"] = str(exc)

    return report


def main() -> None:
    report = asyncio.run(verify())
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
