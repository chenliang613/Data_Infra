"""Abstract base data adapter."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class AbstractDataAdapter(ABC):
    """Reads data from a source and returns records as a list of dicts."""

    @abstractmethod
    async def read(
        self,
        endpoint: str,
        limit: int = 100,
        filters: Dict[str, Any] | None = None,
        masked_columns: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        ...

    @staticmethod
    def _mask(records: List[Dict], masked_columns: List[str]) -> List[Dict]:
        if not masked_columns:
            return records
        result = []
        for row in records:
            masked_row = {
                k: "***MASKED***" if k in masked_columns else v
                for k, v in row.items()
            }
            result.append(masked_row)
        return result
