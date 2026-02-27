"""FastAPI application factory."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ..db.database import init_db
from .routers import assets, audit, contracts, negotiations, parties, transfer


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="DataSpace — 可信可控可管数据交换平台",
        description=(
            "两方通过 Claude Agent 协商数据交换合约，"
            "合约签署后按约定条款安全交换数据，全程哈希链审计。"
        ),
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(parties.router)
    app.include_router(assets.router)
    app.include_router(negotiations.router)
    app.include_router(contracts.router)
    app.include_router(transfer.router)
    app.include_router(audit.router)

    @app.get("/", tags=["Health"])
    async def health() -> dict:
        return {"status": "ok", "service": "DataSpace"}

    return app


app = create_app()
