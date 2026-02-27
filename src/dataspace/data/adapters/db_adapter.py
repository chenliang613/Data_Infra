"""SQLite / SQL database table adapter."""
from __future__ import annotations

from typing import Any, Dict, List

from ...core.exceptions import AdapterError
from .base import AbstractDataAdapter


class DbTableAdapter(AbstractDataAdapter):
    """
    endpoint format: "sqlite:///path/to/db.sqlite::table_name"
    """

    async def read(
        self,
        endpoint: str,
        limit: int = 100,
        filters: Dict[str, Any] | None = None,
        masked_columns: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        try:
            import aiosqlite
        except ImportError as exc:
            raise AdapterError("aiosqlite is required for DB adapter") from exc

        if "::" not in endpoint:
            raise AdapterError(f"DB adapter endpoint must be 'db_path::table_name', got: {endpoint}")

        db_path, table_name = endpoint.split("::", 1)
        db_path = db_path.replace("sqlite:///", "")

        where_clause = ""
        params: List[Any] = []
        if filters:
            conditions = [f"{col} = ?" for col in filters]
            where_clause = "WHERE " + " AND ".join(conditions)
            params = list(filters.values())

        sql = f"SELECT * FROM {table_name} {where_clause} LIMIT ?"
        params.append(limit)

        try:
            async with aiosqlite.connect(db_path) as db:
                db.row_factory = aiosqlite.Row
                async with db.execute(sql, params) as cursor:
                    rows = await cursor.fetchall()
                    records = [dict(row) for row in rows]
        except Exception as exc:
            raise AdapterError(f"DB query failed: {exc}") from exc

        return self._mask(records, masked_columns or [])
