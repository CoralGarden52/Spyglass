from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

Scenario = Literal[
    "general_analysis", "ecommerce", "internet_product", "hardware_iot", "ai_llm", "finance"
]
Mode = Literal["quick", "standard", "deep"]


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginInput(Input):
    email: EmailStr
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.casefold()


class RegisterInput(LoginInput):
    password: SecretStr = Field(min_length=15, max_length=128)
    display_name: str = Field(min_length=1, max_length=80)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Name must not be blank")
        return value.strip()


class UserView(BaseModel):
    id: UUID
    email: str
    display_name: str


class TenantView(BaseModel):
    id: UUID
    name: str
    role: Literal["owner", "admin", "member"]


class Identity(BaseModel):
    schema_version: Literal[1] = 1
    user: UserView
    tenant: TenantView


class ProjectInput(Input):
    title: str = Field(min_length=1, max_length=200)
    mode: Mode = "standard"
    scenario_skill_id: Scenario = "general_analysis"

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Title must not be blank")
        return value.strip()


class ProjectView(ProjectInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    status: str
    created_at: datetime


class ProjectResult(BaseModel):
    schema_version: Literal[1] = 1
    data: ProjectView


class PageMeta(BaseModel):
    total: int
    limit: int
    offset: int


class ProjectList(BaseModel):
    schema_version: Literal[1] = 1
    data: list[ProjectView]
    meta: PageMeta


class ThreadInput(Input):
    project_id: UUID
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return ProjectInput.clean_title(value)


class ThreadView(ThreadInput):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    tenant_id: UUID
    created_at: datetime


class ThreadResult(BaseModel):
    schema_version: Literal[1] = 1
    data: ThreadView


class ThreadList(BaseModel):
    schema_version: Literal[1] = 1
    data: list[ThreadView]


class MessageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    role: str
    content_json: dict[str, Any]
    sequence: int
    created_at: datetime


class MessageList(BaseModel):
    schema_version: Literal[1] = 1
    data: list[MessageView]
