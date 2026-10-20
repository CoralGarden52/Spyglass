from typing import Annotated

from fastapi import APIRouter, Query, Request

from app.agent.skills.models import (
    ConfigUpdate,
    ResolutionResult,
    Selection,
    SkillKind,
    SkillList,
    SkillResult,
)
from app.application.skills import SkillService
from app.core.dependencies import Context, Database, IdempotencyKey, WriteContext

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.get("", response_model=SkillList)
async def list_skills(
    request: Request, db: Database, context: Context, kind: SkillKind | None = None
) -> SkillList:
    return await SkillService(db, context, request.app.state.skills).list(kind)


@router.post("/resolve", response_model=ResolutionResult)
async def resolve_skills(
    payload: Selection, request: Request, db: Database, context: WriteContext
) -> ResolutionResult:
    """Read-only plan preview; does not create or execute a Run."""
    return await SkillService(db, context, request.app.state.skills).resolution(payload)


@router.get("/{skill_id}", response_model=SkillResult)
async def detail(
    skill_id: str,
    request: Request,
    db: Database,
    context: Context,
    version: Annotated[str | None, Query(pattern=r"^\d+\.\d+\.\d+$")] = None,
) -> SkillResult:
    return await SkillService(db, context, request.app.state.skills).detail(skill_id, version)


@router.patch("/{skill_id}/config", response_model=SkillResult)
async def config(
    skill_id: str,
    payload: ConfigUpdate,
    request: Request,
    db: Database,
    context: WriteContext,
    key: IdempotencyKey,
) -> SkillResult:
    return await SkillService(db, context, request.app.state.skills).update(skill_id, payload, key)
