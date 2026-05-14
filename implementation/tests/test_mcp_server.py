import asyncio
import importlib
import json

import pytest


def test_fastmcp_surface_exposes_tools_resources_and_errors(tmp_path, monkeypatch):
    pytest.importorskip("fastmcp")
    monkeypatch.setenv("SQLITE_LAB_DB", str(tmp_path / "lab.db"))

    server = importlib.import_module("implementation.mcp_server")
    server.reset_adapter_for_tests()

    async def exercise_server():
        from fastmcp import Client
        from fastmcp.exceptions import ToolError

        async with Client(server.mcp) as client:
            tools = await client.list_tools()
            assert {tool.name for tool in tools} == {"search", "insert", "aggregate"}

            resources = await client.list_resources()
            assert "schema://database" in {str(resource.uri) for resource in resources}

            templates = await client.list_resource_templates()
            assert "schema://table/{table_name}" in {str(template.uriTemplate) for template in templates}

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
            assert search_result.data["row_count"] == 2
            assert search_result.data["rows"][0]["name"] == "Linh Tran"

            aggregate_result = await client.call_tool(
                "aggregate",
                {"table": "students", "metric": "count", "group_by": "cohort"},
            )
            assert aggregate_result.data["row_count"] >= 2

            content = await client.read_resource("schema://database")
            database_schema = json.loads(content[0].text)
            assert "students" in database_schema["tables"]

            table_content = await client.read_resource("schema://table/students")
            table_schema = json.loads(table_content[0].text)
            assert table_schema["table"] == "students"

            with pytest.raises(ToolError, match="Unknown table"):
                await client.call_tool("search", {"table": "missing_table"})

    asyncio.run(exercise_server())

