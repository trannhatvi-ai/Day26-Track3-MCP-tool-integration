from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


DEFAULT_DB_PATH = Path(__file__).with_name("sqlite_lab.db")


SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS enrollments;
DROP TABLE IF EXISTS courses;
DROP TABLE IF EXISTS students;

CREATE TABLE students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cohort TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    score REAL NOT NULL CHECK (score >= 0 AND score <= 100),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE courses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    credits INTEGER NOT NULL CHECK (credits > 0)
);

CREATE TABLE enrollments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    course_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'completed', 'dropped')),
    grade REAL CHECK (grade IS NULL OR (grade >= 0 AND grade <= 100)),
    enrolled_on TEXT NOT NULL,
    UNIQUE (student_id, course_id),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (course_id) REFERENCES courses(id) ON DELETE CASCADE
);
"""


SEED_SQL = """
INSERT INTO students (id, name, cohort, email, score, created_at) VALUES
    (1, 'An Nguyen', 'A1', 'an.nguyen@example.com', 86.0, '2026-01-10T09:00:00'),
    (2, 'Linh Tran', 'A1', 'linh.tran@example.com', 91.0, '2026-01-11T09:00:00'),
    (3, 'Bao Le', 'A2', 'bao.le@example.com', 79.0, '2026-01-12T09:00:00'),
    (4, 'Mai Do', 'A2', 'mai.do@example.com', 86.0, '2026-01-13T09:00:00'),
    (5, 'Quang Pham', 'A3', 'quang.pham@example.com', 73.5, '2026-01-14T09:00:00');

INSERT INTO courses (id, code, title, credits) VALUES
    (1, 'MCP101', 'MCP Server Foundations', 3),
    (2, 'SQL201', 'Safe SQL for AI Tools', 4),
    (3, 'AGT301', 'Agent Tool Integration', 3);

INSERT INTO enrollments (id, student_id, course_id, status, grade, enrolled_on) VALUES
    (1, 1, 1, 'completed', 88.0, '2026-01-20'),
    (2, 1, 2, 'active', NULL, '2026-02-01'),
    (3, 2, 1, 'completed', 94.0, '2026-01-20'),
    (4, 3, 2, 'active', NULL, '2026-02-01'),
    (5, 4, 3, 'completed', 84.0, '2026-02-15'),
    (6, 5, 3, 'active', NULL, '2026-02-15');
"""


def create_database(path: str | Path = DEFAULT_DB_PATH) -> Path:
    """Create a fresh SQLite database with deterministic schema and seed data."""
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA_SQL)
        conn.executescript(SEED_SQL)
        conn.commit()

    return db_path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the SQLite lab database.")
    parser.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help="SQLite database path. Defaults to implementation/sqlite_lab.db.",
    )
    args = parser.parse_args()

    db_path = create_database(args.db_path)
    print(f"Created database at {db_path}")


if __name__ == "__main__":
    main()

