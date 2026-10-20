from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent.skills.contracts import SCHEMAS, schema_document
from app.agent.skills.models import CORE_IDS
from app.agent.skills.registry import SkillRegistry
from app.application.auth import TenantContext
from app.domain.errors import DomainError
from app.infrastructure.database.accounts import Tenant
from app.infrastructure.database.skills import SkillConfig, SkillMutation, SkillVersion


class SkillRepository:
    def __init__(self, database: AsyncSession, context: TenantContext) -> None:
        self.database = database
        self.context = context

    async def ensure_catalogue(self, registry: SkillRegistry) -> None:
        values = []
        for definition in registry.all():
            manifest = definition.manifest
            values.append(
                {
                    "id": manifest.id,
                    "version": manifest.version,
                    "kind": manifest.kind,
                    "manifest_checksum": definition.checksum,
                    "instructions": definition.instructions,
                    "is_system_required": manifest.id in CORE_IDS,
                    "metadata_json": {
                        "manifest": manifest.model_dump(mode="json"),
                        "input_json_schema": schema_document(manifest.input_schema),
                        "output_json_schema": schema_document(manifest.output_schema),
                        "config_json_schema": schema_document(manifest.config_schema),
                        "default_config": SCHEMAS[manifest.config_schema]().model_dump(mode="json"),
                    },
                }
            )
        await self.database.execute(insert(SkillVersion).values(values).on_conflict_do_nothing())
        for definition in registry.all():
            saved = await self.version(definition.manifest.id, definition.manifest.version)
            if saved is None or saved.manifest_checksum != definition.checksum:
                raise DomainError(
                    409, "skill_version_conflict", "同一 Skill 版本的内容已改变，请提升版本号后重试"
                )

    async def version(self, skill_id: str, version: str) -> SkillVersion | None:
        return await self.database.get(SkillVersion, (skill_id, version))

    async def configs(self) -> dict[str, SkillConfig]:
        rows = await self.database.scalars(
            select(SkillConfig).where(SkillConfig.tenant_id == self.context.tenant_id)
        )
        return {row.skill_id: row for row in rows}

    async def lock_tenant(self) -> None:
        await self.database.execute(
            select(Tenant.id).where(Tenant.id == self.context.tenant_id).with_for_update()
        )

    async def mutation(self, key: str) -> SkillMutation | None:
        return cast(
            SkillMutation | None,
            await self.database.get(
                SkillMutation, (self.context.tenant_id, self.context.user_id, key)
            ),
        )
