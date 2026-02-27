"""Streaming data adapter (simulated via in-memory generator)."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Dict, List

from ...core.exceptions import AdapterError
from .base import AbstractDataAdapter


class StreamAdapter(AbstractDataAdapter):
    """
    Simple streaming adapter: reads a JSON-lines file or simulates a live stream.
    endpoint: path to a .jsonl file, or "stream://simulate" for synthetic data.
    """

    async def read(
        self,
        endpoint: str,
        limit: int = 100,
        filters: Dict[str, Any] | None = None,
        masked_columns: List[str] | None = None,
    ) -> List[Dict[str, Any]]:
        records = []
        async for record in self._stream(endpoint, limit):
            records.append(record)
        return self._mask(records, masked_columns or [])

    async def _stream(self, endpoint: str, limit: int) -> AsyncGenerator[Dict, None]:
        if endpoint == "stream://simulate":
            for i in range(limit):
                await asyncio.sleep(0)  # yield control
                yield {
                    "seq": i,
                    "event": "pageview",
                    "user_id": f"user_{i % 100}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "page": f"/products/{i % 20}",
                }
        else:
            from pathlib import Path
            import json
            path = Path(endpoint)
            if not path.exists():
                raise AdapterError(f"Stream file not found: {endpoint}")
            count = 0
            with path.open() as f:
                for line in f:
                    if count >= limit:
                        break
                    line = line.strip()
                    if line:
                        yield json.loads(line)
                        count += 1
