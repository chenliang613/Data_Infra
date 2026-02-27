"""CSV / Parquet file adapter."""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List

from ...core.exceptions import AdapterError
from .base import AbstractDataAdapter


class FileAdapter(AbstractDataAdapter):
    async def read(
        self,
        endpoint: str,
        limit: int = 100,
        filters: Dict[str, Any] | None = None,
        masked_columns: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        path = Path(endpoint)
        if not path.exists():
            raise AdapterError(f"File not found: {endpoint}")

        suffix = path.suffix.lower()
        try:
            if suffix == ".parquet":
                records = self._read_parquet(path, limit, filters)
            else:
                records = self._read_csv(path, limit, filters)
        except AdapterError:
            raise
        except Exception as exc:
            raise AdapterError(f"Failed to read file '{endpoint}': {exc}") from exc

        return self._mask(records, masked_columns or [])

    def _read_csv(self, path: Path, limit: int, filters: Dict | None) -> List[Dict]:
        records = []
        with path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                if len(records) >= limit:
                    break
                if filters:
                    match = all(str(row.get(k, "")) == str(v) for k, v in filters.items())
                    if not match:
                        continue
                records.append(dict(row))
        return records

    def _read_parquet(self, path: Path, limit: int, filters: Dict | None) -> List[Dict]:
        try:
            import pandas as pd
            df = pd.read_parquet(path)
            if filters:
                for col, val in filters.items():
                    if col in df.columns:
                        df = df[df[col] == val]
            return df.head(limit).to_dict(orient="records")
        except ImportError as exc:
            raise AdapterError("pandas is required for Parquet files") from exc
