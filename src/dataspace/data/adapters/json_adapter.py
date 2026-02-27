"""JSON / REST API adapter."""
from __future__ import annotations

from typing import Any, Dict, List

import httpx

from ...core.exceptions import AdapterError
from .base import AbstractDataAdapter


class JsonApiAdapter(AbstractDataAdapter):
    async def read(
        self,
        endpoint: str,
        limit: int = 100,
        filters: Dict[str, Any] | None = None,
        masked_columns: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"limit": limit}
        if filters:
            params.update(filters)
        async with httpx.AsyncClient(timeout=30) as client:
            try:
                resp = await client.get(endpoint, params=params)
                resp.raise_for_status()
                data = resp.json()
            except Exception as exc:
                raise AdapterError(f"JSON API fetch failed: {exc}") from exc

        if isinstance(data, list):
            records = data[:limit]
        elif isinstance(data, dict):
            # Try common wrapper keys
            for key in ("data", "results", "items", "records"):
                if key in data and isinstance(data[key], list):
                    records = data[key][:limit]
                    break
            else:
                records = [data]
        else:
            records = []

        return self._mask(records, masked_columns or [])
