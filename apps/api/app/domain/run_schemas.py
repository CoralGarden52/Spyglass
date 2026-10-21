from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.agent.skills.models import Selection


class RunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    thread_id: UUID
    project_id: UUID
    status: str
    error_code: str | None
    requested_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    usage_json: dict[str, Any] | None
    report_id: UUID | None = None
    selection: Selection = Field(default_factory=Selection)


class RunResponse(BaseModel):
    schema_version: Literal[1] = 1
    data: RunView


class RunCreated(RunResponse):
    events_url: str


class RunList(BaseModel):
    schema_version: Literal[1] = 1
    data: list[RunView]


class RunEventView(BaseModel):
    event_id: UUID
    schema_version: Literal[1] = 1
    seq: int
    run_id: UUID
    thread_id: UUID
    type: str
    timestamp: datetime
    payload: dict[str, Any]


class EventList(BaseModel):
    schema_version: Literal[1] = 1
    data: list[RunEventView]


class EmptyCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
