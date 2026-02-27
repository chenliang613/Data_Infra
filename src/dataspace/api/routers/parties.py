"""Party registration endpoints."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.enums import PartyRole
from ...core.models import Party
from ...db.database import get_session
from ...db.repositories import party_repo

router = APIRouter(prefix="/parties", tags=["Parties"])


class PartyCreate(BaseModel):
    name: str
    description: str = ""
    role: PartyRole
    public_key_pem: str = ""
    endpoint: str = ""


@router.post("", response_model=Party, status_code=201)
async def create_party(data: PartyCreate) -> Party:
    party = Party(**data.model_dump())
    async with get_session() as session:
        return await party_repo.create(session, party)


@router.get("", response_model=List[Party])
async def list_parties() -> List[Party]:
    async with get_session() as session:
        return await party_repo.list_all(session)


@router.get("/{party_id}", response_model=Party)
async def get_party(party_id: str) -> Party:
    async with get_session() as session:
        party = await party_repo.get(session, party_id)
    if not party:
        raise HTTPException(status_code=404, detail="Party not found")
    return party
