"""In-memory stand-in for the SQLAlchemy calls the auth tests make.

CI does not start Postgres. The matcher covers equality, IS NULL, ILIKE, and OR.
"""

from __future__ import annotations

import re
import uuid
from typing import Any


def _op_name(operator: object) -> str:
    return getattr(operator, "__name__", "") or ""


def _literal(right: object) -> object:
    if right is None:
        return None
    if type(right).__name__ == "Null":
        return None
    if type(right).__name__ == "BindParameter":
        return getattr(right, "value", None)
    return right


def _column_key(left: object) -> str | None:
    key = getattr(left, "key", None)
    if isinstance(key, str):
        return key
    element = getattr(left, "element", None)
    nested = getattr(element, "key", None)
    return nested if isinstance(nested, str) else None


def _ilike(value: object, pattern: str) -> bool:
    if value is None:
        return False
    parts: list[str] = []
    for char in pattern:
        if char == "%":
            parts.append(".*")
        elif char == "_":
            parts.append(".")
        else:
            parts.append(re.escape(char))
    return re.search("(?i)" + "".join(parts) + r"\Z", str(value)) is not None


def matches(row: object, clause: object) -> bool:
    operator = _op_name(getattr(clause, "operator", None))
    nested = getattr(clause, "clauses", None)
    if nested is not None and operator in {"or_", "and_"}:
        items = list(nested)
        if operator == "or_":
            return any(matches(row, item) for item in items)
        return all(matches(row, item) for item in items)
    key = _column_key(getattr(clause, "left", None))
    if key is None:
        raise AssertionError(f"Unhandled clause {clause!r} op={operator}")
    value = _literal(getattr(clause, "right", None))
    current = getattr(row, key, None)
    if operator in {"eq", "is_"}:
        if current is None or value is None:
            return current is None and value is None
        return str(current) == str(value)
    if operator in {"ilike_op", "like_op"}:
        return _ilike(current, "" if value is None else str(value))
    raise AssertionError(f"Unhandled operator {operator} on {clause!r}")


class Query:
    def __init__(self, db: "MemoryDB", model: type) -> None:
        self.db = db
        self.model = model
        self._clauses: list[object] = []
        self._order: list[tuple[str, bool]] = []
        self._limit: int | None = None
        self._offset = 0

    def filter(self, *clauses: object) -> "Query":
        self._clauses.extend(clauses)
        return self

    def order_by(self, *clauses: object) -> "Query":
        for clause in clauses:
            element = getattr(clause, "element", clause)
            key = _column_key(element) or _column_key(clause)
            if not key:
                continue
            modifier = _op_name(getattr(clause, "modifier", None))
            self._order.append((key, modifier.startswith("desc")))
        return self

    def limit(self, count: int) -> "Query":
        self._limit = count
        return self

    def offset(self, count: int) -> "Query":
        self._offset = count
        return self

    def _filtered(self) -> list[object]:
        rows = [row for row in self.db.rows if isinstance(row, self.model)]
        for clause in self._clauses:
            rows = [row for row in rows if matches(row, clause)]
        for key, descending in reversed(self._order):
            rows.sort(key=lambda row: (getattr(row, key) is None, str(getattr(row, key) or "")), reverse=descending)
        return rows

    def count(self) -> int:
        return len(self._filtered())

    def all(self) -> list[object]:
        rows = self._filtered()
        start = self._offset
        end = None if self._limit is None else start + self._limit
        return rows[start:end]

    def first(self) -> object | None:
        rows = self.all()
        return rows[0] if rows else None


class MemoryDB:
    def __init__(self) -> None:
        self.rows: list[object] = []

    def query(self, model: type) -> Query:
        return Query(self, model)

    def add(self, obj: object) -> None:
        if obj not in self.rows:
            self.rows.append(obj)

    def flush(self) -> None:
        for obj in self.rows:
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", uuid.uuid4())

    def commit(self) -> None:
        self.flush()

    def refresh(self, obj: object) -> None:
        return None

    def rollback(self) -> None:
        return None

    def close(self) -> None:
        return None

    def execute(self, *_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("MemoryDB does not execute raw SQL")
