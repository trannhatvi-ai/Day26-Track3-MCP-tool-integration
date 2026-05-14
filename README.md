# FastMCP SQLite Database MCP Server

This repository contains a complete reference implementation for the Day 26 Track 3 lab: a FastMCP server that exposes a small SQLite database through safe `search`, `insert`, and `aggregate` tools, plus schema resources.

## What Is Implemented

- FastMCP server in `implementation/mcp_server.py`
- SQLite adapter in `implementation/db.py`
- Reproducible database schema and seed data in `implementation/init_db.py`
- Tools:
  - `search`
  - `insert`
  - `aggregate`
- Resources:
  - `schema://database`
  - `schema://table/{table_name}`
- Validation for unknown tables, unknown columns, unsupported filter operators, invalid aggregate requests, and empty inserts
- Automated pytest coverage and a repeatable FastMCP verification script
- MCP Inspector and MCP client configuration examples

## Project Structure

```text
implementation/
  __init__.py
  db.py
  init_db.py
  mcp_server.py
  verify_server.py
  start_inspector.ps1
  start_inspector.sh
  client-configs/
    claude-mcp.json
    codex-config.toml
    gemini-settings.json
  tests/
    test_db.py
    test_mcp_server.py
requirements.txt
pytest.ini
```

## Setup

On Windows, use the Python launcher:

```powershell
py -m pip install -r requirements.txt
py -m implementation.init_db
```

On macOS/Linux:

```bash
python -m pip install -r requirements.txt
python -m implementation.init_db
```

By default, the database is created at `implementation/sqlite_lab.db`. You can override it with `SQLITE_LAB_DB`.

## Run The MCP Server

Stdio transport is the default and is the right mode for MCP clients:

```powershell
py implementation/mcp_server.py
```

For a localhost HTTP demo:

```powershell
py implementation/mcp_server.py --transport http --host 127.0.0.1 --port 8000 --path /mcp
```

HTTP endpoint:

```text
http://127.0.0.1:8000/mcp
```

## Verify The Server

Run the automated verification script:

```powershell
py -m implementation.verify_server
```

It checks:

- tool discovery
- resource discovery
- valid `search`
- valid `insert`
- valid `aggregate`
- full schema resource
- invalid request error handling

Run the pytest suite:

```powershell
New-Item -ItemType Directory -Force -Path .tmp | Out-Null
$env:TMP=(Resolve-Path .tmp).Path
$env:TEMP=(Resolve-Path .tmp).Path
py -m pytest
```

The local `TMP/TEMP` assignment avoids Windows temp-folder permission problems on some machines.

## Tool Examples

### Search Students In Cohort A1

```json
{
  "table": "students",
  "filters": { "cohort": "A1" },
  "columns": ["name", "cohort", "score"],
  "order_by": "score",
  "descending": true,
  "limit": 2
}
```

### Insert A Student

```json
{
  "table": "students",
  "values": {
    "name": "Minh Pham",
    "cohort": "A3",
    "email": "minh.pham@example.com",
    "score": 91.0
  }
}
```

### Average Score By Cohort

```json
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort"
}
```

### Invalid Request Demo

```json
{
  "table": "missing_table"
}
```

Expected error includes:

```text
Unknown table 'missing_table'
```

## Resource Examples

Full schema:

```text
schema://database
```

Single table schema:

```text
schema://table/students
```

## MCP Inspector Demo

Use MCP Inspector when you need localhost screenshots for the lab submission.

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File implementation/start_inspector.ps1
```

macOS/Linux:

```bash
bash implementation/start_inspector.sh
```

The Inspector command starts a local web UI. In the UI, connect to the stdio server, verify the three tools, read `schema://database`, and capture screenshots of successful and failing tool calls.

## Client Configuration Examples

Examples live in `implementation/client-configs/`.

Use absolute paths when copying these into real client config files. For Windows with the Python launcher, this pattern is usually enough:

```json
{
  "command": "py",
  "args": ["D:/ABSOLUTE/PATH/TO/implementation/mcp_server.py"]
}
```

For macOS/Linux:

```json
{
  "command": "python",
  "args": ["/ABSOLUTE/PATH/TO/implementation/mcp_server.py"]
}
```

## Data Model

The seeded database contains:

- `students`: names, cohorts, email addresses, and scores
- `courses`: course code, title, and credits
- `enrollments`: student/course join records with status and grade

The adapter validates identifiers against SQLite schema metadata before building SQL and uses bound parameters for values.

