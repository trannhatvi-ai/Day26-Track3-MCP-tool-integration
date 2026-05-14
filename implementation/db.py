from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any


class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""


SUPPORTED_FILTER_OPERATORS = {
    "eq": "=",
    "ne": "!=",
    "gt": ">",
    "gte": ">=",
    "lt": "<",
    "lte": "<=",
    "like": "LIKE",
    "in": "IN",
}

SUPPORTED_AGGREGATES = {"count", "avg", "sum", "min", "max"}
NUMERIC_TYPES = ("INT", "REAL", "NUM", "DEC", "DOUBLE", "FLOAT")


class SQLiteAdapter:
    """Safe, small database adapter used by the MCP tools."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                  AND name NOT LIKE 'sqlite_%'
                ORDER BY name
                """
            ).fetchall()
        return [row["name"] for row in rows]

    def get_table_schema(self, table: str) -> dict[str, Any]:
        table = self._validate_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()
            row_count = conn.execute(
                f"SELECT COUNT(*) AS count FROM {self._quote_identifier(table)}"
            ).fetchone()["count"]

        return {
            "table": table,
            "row_count": row_count,
            "columns": [
                {
                    "name": row["name"],
                    "type": row["type"],
                    "not_null": bool(row["notnull"]),
                    "default": row["dflt_value"],
                    "primary_key": bool(row["pk"]),
                }
                for row in rows
            ],
        }

    def describe_database(self) -> dict[str, Any]:
        return {
            "database_path": str(self.db_path.resolve()),
            "tables": {table: self.get_table_schema(table) for table in self.list_tables()},
        }

    def search(
        self,
        table: str,
        columns: list[str] | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        limit: int = 20,
        offset: int = 0,
        order_by: str | None = None,
        descending: bool = False,
    ) -> dict[str, Any]:
        table = self._validate_table(table)
        schema_columns = self._column_map(table)
        selected_columns = self._validate_columns(table, columns, allow_empty=False)
        limit = self._validate_limit(limit)
        offset = self._validate_offset(offset)

        where_sql, params, normalized_filters = self._build_where(table, filters)
        projection = (
            "*"
            if selected_columns is None
            else ", ".join(self._quote_identifier(column) for column in selected_columns)
        )
        sql = f"SELECT {projection} FROM {self._quote_identifier(table)}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        if order_by is not None:
            if order_by not in schema_columns:
                raise ValidationError(f"Unknown column '{order_by}' for table '{table}'")
            direction = "DESC" if descending else "ASC"
            sql += f" ORDER BY {self._quote_identifier(order_by)} {direction}"
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        return {
            "table": table,
            "columns": selected_columns or "all",
            "filters": normalized_filters,
            "limit": limit,
            "offset": offset,
            "order_by": order_by,
            "descending": bool(descending),
            "row_count": len(rows),
            "rows": rows,
        }

    def insert(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        table = self._validate_table(table)
        if not isinstance(values, dict) or not values:
            raise ValidationError("Insert values cannot be empty")

        schema_columns = self._column_map(table)
        unknown_columns = [column for column in values if column not in schema_columns]
        if unknown_columns:
            raise ValidationError(
                f"Unknown column '{unknown_columns[0]}' for table '{table}'"
            )

        columns = list(values.keys())
        quoted_columns = ", ".join(self._quote_identifier(column) for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        sql = f"INSERT INTO {self._quote_identifier(table)} ({quoted_columns}) VALUES ({placeholders})"

        try:
            with self.connect() as conn:
                cursor = conn.execute(sql, [values[column] for column in columns])
                inserted_id = cursor.lastrowid
                conn.commit()
                inserted = dict(
                    conn.execute(
                        f"SELECT * FROM {self._quote_identifier(table)} WHERE rowid = ?",
                        (inserted_id,),
                    ).fetchone()
                )
        except sqlite3.IntegrityError as exc:
            raise ValidationError(f"Insert failed: {exc}") from exc

        return {"table": table, "inserted": inserted}

    def aggregate(
        self,
        table: str,
        metric: str,
        column: str | None = None,
        filters: dict[str, Any] | list[dict[str, Any]] | None = None,
        group_by: str | list[str] | None = None,
    ) -> dict[str, Any]:
        table = self._validate_table(table)
        metric = metric.lower().strip() if isinstance(metric, str) else ""
        if metric not in SUPPORTED_AGGREGATES:
            raise ValidationError(f"Unsupported aggregate metric '{metric}'")

        schema_columns = self._column_map(table)
        if column is not None and column not in schema_columns:
            raise ValidationError(f"Unknown column '{column}' for table '{table}'")

        if metric == "count":
            aggregate_expr = "COUNT(*)" if column is None else f"COUNT({self._quote_identifier(column)})"
        else:
            if column is None:
                raise ValidationError(f"Aggregate metric '{metric}' requires a column")
            if metric in {"avg", "sum"} and not self._is_numeric(schema_columns[column]["type"]):
                raise ValidationError(
                    f"Aggregate metric '{metric}' requires a numeric column"
                )
            aggregate_expr = f"{metric.upper()}({self._quote_identifier(column)})"

        group_columns = self._normalize_group_by(table, group_by)
        select_parts = [self._quote_identifier(column_name) for column_name in group_columns]
        select_parts.append(f"{aggregate_expr} AS value")

        where_sql, params, normalized_filters = self._build_where(table, filters)
        sql = f"SELECT {', '.join(select_parts)} FROM {self._quote_identifier(table)}"
        if where_sql:
            sql += f" WHERE {where_sql}"
        if group_columns:
            sql += " GROUP BY " + ", ".join(self._quote_identifier(column_name) for column_name in group_columns)
            sql += " ORDER BY " + ", ".join(self._quote_identifier(column_name) for column_name in group_columns)

        with self.connect() as conn:
            rows = [dict(row) for row in conn.execute(sql, params).fetchall()]

        return {
            "table": table,
            "metric": metric,
            "column": column,
            "group_by": group_columns or None,
            "filters": normalized_filters,
            "row_count": len(rows),
            "rows": rows,
        }

    def _validate_table(self, table: str) -> str:
        if not isinstance(table, str) or not table.strip():
            raise ValidationError("Table name is required")
        table = table.strip()
        if table not in self.list_tables():
            raise ValidationError(f"Unknown table '{table}'")
        return table

    def _column_map(self, table: str) -> dict[str, dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({self._quote_identifier(table)})").fetchall()
        return {
            row["name"]: {
                "type": row["type"],
                "not_null": bool(row["notnull"]),
                "primary_key": bool(row["pk"]),
            }
            for row in rows
        }

    def _validate_columns(
        self,
        table: str,
        columns: list[str] | None,
        allow_empty: bool,
    ) -> list[str] | None:
        if columns is None:
            return None
        if not isinstance(columns, list):
            raise ValidationError("Columns must be a list of column names")
        if not columns and not allow_empty:
            raise ValidationError("Columns cannot be empty")

        schema_columns = self._column_map(table)
        for column in columns:
            if column not in schema_columns:
                raise ValidationError(f"Unknown column '{column}' for table '{table}'")
        return columns

    def _build_where(
        self,
        table: str,
        filters: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> tuple[str, list[Any], list[dict[str, Any]]]:
        normalized_filters = self._normalize_filters(filters)
        schema_columns = self._column_map(table)
        clauses: list[str] = []
        params: list[Any] = []

        for item in normalized_filters:
            column = item["column"]
            operator = item["op"]
            value = item["value"]

            if column not in schema_columns:
                raise ValidationError(f"Unknown column '{column}' for table '{table}'")
            if operator not in SUPPORTED_FILTER_OPERATORS:
                raise ValidationError(f"Unsupported filter operator '{operator}'")

            quoted_column = self._quote_identifier(column)
            sql_operator = SUPPORTED_FILTER_OPERATORS[operator]
            if operator == "in":
                if not isinstance(value, (list, tuple)) or not value:
                    raise ValidationError("Filter operator 'in' requires a non-empty list")
                placeholders = ", ".join("?" for _ in value)
                clauses.append(f"{quoted_column} IN ({placeholders})")
                params.extend(value)
            else:
                clauses.append(f"{quoted_column} {sql_operator} ?")
                params.append(value)

        return " AND ".join(clauses), params, normalized_filters

    def _normalize_filters(
        self,
        filters: dict[str, Any] | list[dict[str, Any]] | None,
    ) -> list[dict[str, Any]]:
        if filters is None:
            return []
        if isinstance(filters, dict):
            normalized = []
            for column, value in filters.items():
                if isinstance(value, dict):
                    normalized.append(
                        {
                            "column": column,
                            "op": value.get("op", "eq"),
                            "value": value.get("value"),
                        }
                    )
                else:
                    normalized.append({"column": column, "op": "eq", "value": value})
            return normalized
        if isinstance(filters, list):
            normalized = []
            for item in filters:
                if not isinstance(item, dict):
                    raise ValidationError("Each filter must be an object")
                normalized.append(
                    {
                        "column": item.get("column"),
                        "op": item.get("op", "eq"),
                        "value": item.get("value"),
                    }
                )
            return normalized
        raise ValidationError("Filters must be an object or a list of filter objects")

    def _normalize_group_by(self, table: str, group_by: str | list[str] | None) -> list[str]:
        if group_by is None:
            return []
        group_columns = [group_by] if isinstance(group_by, str) else group_by
        if not isinstance(group_columns, list) or not group_columns:
            raise ValidationError("group_by must be a column name or list of column names")

        schema_columns = self._column_map(table)
        for column in group_columns:
            if column not in schema_columns:
                raise ValidationError(f"Unknown column '{column}' for table '{table}'")
        return group_columns

    def _validate_limit(self, limit: int) -> int:
        if not isinstance(limit, int):
            raise ValidationError("Limit must be an integer")
        if limit < 1 or limit > 100:
            raise ValidationError("Limit must be between 1 and 100")
        return limit

    def _validate_offset(self, offset: int) -> int:
        if not isinstance(offset, int) or offset < 0:
            raise ValidationError("Offset must be a non-negative integer")
        return offset

    def _is_numeric(self, declared_type: str) -> bool:
        return any(token in declared_type.upper() for token in NUMERIC_TYPES)

    def _quote_identifier(self, identifier: str) -> str:
        return '"' + identifier.replace('"', '""') + '"'

