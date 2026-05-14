from pathlib import Path

import pytest

from implementation.db import SQLiteAdapter, ValidationError
from implementation.init_db import create_database


def build_adapter(tmp_path: Path) -> SQLiteAdapter:
    db_path = tmp_path / "lab.db"
    create_database(db_path)
    return SQLiteAdapter(db_path)


def test_search_filters_orders_and_paginates_rows(tmp_path):
    adapter = build_adapter(tmp_path)

    result = adapter.search(
        "students",
        columns=["name", "cohort", "score"],
        filters={"cohort": "A1"},
        order_by="score",
        descending=True,
        limit=2,
        offset=0,
    )

    assert result["table"] == "students"
    assert result["row_count"] == 2
    assert [row["name"] for row in result["rows"]] == ["Linh Tran", "An Nguyen"]
    assert all(row["cohort"] == "A1" for row in result["rows"])


def test_insert_returns_inserted_payload_with_generated_id(tmp_path):
    adapter = build_adapter(tmp_path)

    result = adapter.insert(
        "students",
        {
            "name": "Minh Pham",
            "cohort": "A3",
            "email": "minh.pham@example.com",
            "score": 91.0,
        },
    )

    assert result["table"] == "students"
    assert result["inserted"]["id"] > 0
    assert result["inserted"]["name"] == "Minh Pham"
    assert result["inserted"]["cohort"] == "A3"


def test_aggregate_supports_average_by_group(tmp_path):
    adapter = build_adapter(tmp_path)

    result = adapter.aggregate("students", metric="avg", column="score", group_by="cohort")

    rows = {row["cohort"]: row["value"] for row in result["rows"]}
    assert rows["A1"] == pytest.approx(88.5)
    assert rows["A2"] == pytest.approx(82.5)


def test_invalid_requests_are_rejected_before_sql_execution(tmp_path):
    adapter = build_adapter(tmp_path)

    with pytest.raises(ValidationError, match="Unknown table"):
        adapter.search("missing_table")

    with pytest.raises(ValidationError, match="Unknown column"):
        adapter.search("students", filters={"not_a_column": "x"})

    with pytest.raises(ValidationError, match="Unsupported filter operator"):
        adapter.search("students", filters={"score": {"op": "regex", "value": "9.*"}})

    with pytest.raises(ValidationError, match="Insert values cannot be empty"):
        adapter.insert("students", {})

    with pytest.raises(ValidationError, match="requires a column"):
        adapter.aggregate("students", metric="avg")

