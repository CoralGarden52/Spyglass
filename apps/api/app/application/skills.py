import hashlib
import json
from datetime import UTC, datetime
from typing import Any

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills.contracts import SCHEMAS, schema_document
from app.agent.skills.models import (
    CORE_IDS,
    ConfigUpdate,
    ResolutionResult,
    Selection,
    SkillDetail,
    SkillList,
    SkillResult,
    SkillView,
)
from app.agent.skills.registry import SkillRegistry
from app.agent.skills.resolver import resolve
from app.application.auth import TenantContext
from app.domain.errors import DomainError
from app.infrastructure.database.skills import SkillConfig, SkillMutation
from app.infrastructure.skill_repository import SkillRepository


class SkillService:
    def __init__(
        self, database: AsyncSession, context: TenantContext, registry: SkillRegistry
    ) -> None:
        self.database = database
        self.context = context
        self.registry = registry
        self.repository = SkillRepository(database, context)

    def validated_config(self, skill_id: str, config: dict[str, Any]) -> dict[str, Any]:
        definition = self.registry.get(skill_id)
        try:
            return (
                SCHEMAS[definition.manifest.config_schema]
                .model_validate(config)
                .model_dump(mode="json")
            )
        except ValidationError:
            raise DomainError(
                422, "invalid_skill_config", "配置字段或范围不符合 Skill Schema"
            ) from None

    async def views(self) -> dict[str, SkillView]:
        configs = await self.repository.configs()
        result = {}
        for definition in self.registry.all():
            m = definition.manifest
            saved = configs.get(m.id)
            migrating = saved is not None and saved.skill_version != m.version
            try:
                config = self.validated_config(m.id, saved.config_json if saved else {})
            except DomainError:
                if not migrating:
                    raise
                # Proposed defaults are explicit and cannot be resolved until acknowledged.
                config = self.validated_config(m.id, {})
            result[m.id] = SkillView(
                id=m.id,
                name=m.name,
                description=m.description,
                kind=m.kind,
                version=m.version,
                manifest_checksum=definition.checksum,
                is_system_required=m.id in CORE_IDS,
                enabled=saved.enabled if saved else True,
                revision=saved.revision if saved else 0,
                config_version=saved.skill_version if saved else m.version,
                config_status="migration_required" if migrating else "current",
                config=config,
                allowed_tools=list(m.allowed_tools),
                applies_to=list(m.applies_to),
                requires=list(m.requires),
                dimensions=list(m.dimensions),
            )
        return result

    async def list(self, kind: str | None = None) -> SkillList:
        await self.repository.ensure_catalogue(self.registry)
        views = await self.views()
        await self.database.commit()
        return SkillList(
            data=[item for item in views.values() if kind is None or item.kind == kind]
        )

    async def detail(self, skill_id: str, version: str | None = None) -> SkillResult:
        definition = self.registry.get(skill_id)
        await self.repository.ensure_catalogue(self.registry)
        m = definition.manifest
        if version is not None and version != m.version:
            stored = await self.repository.version(skill_id, version)
            if stored is None:
                raise DomainError(404, "skill_version_not_found", "技能历史版本不存在")
            metadata = stored.metadata_json
            old = metadata["manifest"]
            view = SkillView(
                id=old["id"],
                name=old["name"],
                description=old["description"],
                kind=old["kind"],
                version=old["version"],
                manifest_checksum=stored.manifest_checksum,
                is_system_required=stored.is_system_required,
                enabled=True,
                revision=0,
                config_version=old["version"],
                config=metadata["default_config"],
                allowed_tools=old["allowed_tools"],
                applies_to=old["applies_to"],
                requires=old["requires"],
                dimensions=old["dimensions"],
            )
            result = SkillDetail(
                **view.model_dump(),
                instructions=stored.instructions,
                input_json_schema=metadata["input_json_schema"],
                output_json_schema=metadata["output_json_schema"],
                config_json_schema=metadata["config_json_schema"],
            )
        else:
            view = (await self.views())[skill_id]
            result = SkillDetail(
                **view.model_dump(),
                instructions=definition.instructions,
                input_json_schema=schema_document(m.input_schema),
                output_json_schema=schema_document(m.output_schema),
                config_json_schema=schema_document(m.config_schema),
            )
        await self.database.commit()
        return SkillResult(data=result)

    async def update(self, skill_id: str, payload: ConfigUpdate, key: str) -> SkillResult:
        definition = self.registry.get(skill_id)
        if payload.enabled is False and definition.manifest.kind != "advanced":
            code = "required_skill" if skill_id in CORE_IDS else "scenario_always_available"
            raise DomainError(409, code, "基础分析不可关闭；场景通过主场景单选切换")
        if payload.config is None and payload.enabled is None:
            raise DomainError(422, "empty_skill_update", "请提供启用状态或配置")
        await self.repository.ensure_catalogue(self.registry)
        await self.repository.lock_tenant()
        checksum = hashlib.sha256(
            (
                skill_id
                + "\0"
                + json.dumps(payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
            ).encode()
        ).hexdigest()
        previous = await self.repository.mutation(key)
        if previous is not None:
            if previous.request_hash != checksum:
                raise DomainError(409, "idempotency_conflict", "幂等键已用于其他 Skill 配置请求")
            await self.database.commit()
            return SkillResult.model_validate(previous.response_json)
        current = (await self.views())[skill_id]
        if payload.expected_revision != current.revision:
            raise DomainError(409, "skill_config_conflict", "配置已被更新，请刷新后重试")
        if current.config_status == "migration_required" and payload.config is None:
            raise DomainError(
                409, "skill_config_migration_required", "技能版本已更新，请确认新版本配置后保存"
            )
        config = self.validated_config(
            skill_id, payload.config if payload.config is not None else current.config
        )
        row = await self.database.get(SkillConfig, (self.context.tenant_id, skill_id))
        if row is None:
            row = SkillConfig(tenant_id=self.context.tenant_id, skill_id=skill_id)
            self.database.add(row)
        row.skill_version = definition.manifest.version
        row.enabled = current.enabled if payload.enabled is None else payload.enabled
        row.config_json = config
        row.revision = current.revision + 1
        row.updated_at = datetime.now(UTC)
        await self.database.flush()
        m = definition.manifest
        view = (await self.views())[skill_id]
        result = SkillResult(
            data=SkillDetail(
                **view.model_dump(),
                instructions=definition.instructions,
                input_json_schema=schema_document(m.input_schema),
                output_json_schema=schema_document(m.output_schema),
                config_json_schema=schema_document(m.config_schema),
            )
        )
        self.database.add(
            SkillMutation(
                tenant_id=self.context.tenant_id,
                user_id=self.context.user_id,
                idempotency_key=key,
                request_hash=checksum,
                response_json=result.model_dump(mode="json"),
            )
        )
        await self.database.commit()
        return result

    async def resolution(self, selection: Selection, *, commit: bool = True) -> ResolutionResult:
        await self.repository.ensure_catalogue(self.registry)
        result = ResolutionResult(data=resolve(self.registry, selection, await self.views()))
        if commit:
            await self.database.commit()
        return result
