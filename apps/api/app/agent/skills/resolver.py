from typing import Literal

from app.agent.skills.models import CORE_IDS, Resolution, Selection, SkillView, Snapshot
from app.agent.skills.registry import SkillRegistry
from app.domain.errors import DomainError


def resolve(
    registry: SkillRegistry, selection: Selection, configs: dict[str, SkillView]
) -> Resolution:
    scenario = registry.get(selection.scenario_skill_id).manifest
    automatic = selection.advanced_skill_selection == "auto"
    chosen = (
        list(scenario.recommended_advanced.get(selection.mode, ()))
        if automatic
        else selection.advanced_skill_ids
    )
    if automatic:
        chosen = [skill_id for skill_id in chosen if configs[skill_id].enabled]
    snapshots = []
    for skill_id in [selection.scenario_skill_id, *CORE_IDS, *chosen]:
        definition = registry.get(skill_id)
        manifest = definition.manifest
        config = configs[skill_id]
        if config.config_status == "migration_required":
            raise DomainError(
                409,
                "skill_config_migration_required",
                f"技能“{manifest.name}”已更新，请到技能中心确认并保存新版本配置",
            )
        if not config.enabled:
            raise DomainError(409, "skill_disabled", f"技能“{manifest.name}”已在工作空间停用")
        source: Literal["manual", "auto", "required"] = (
            "required"
            if manifest.kind == "core"
            else "auto"
            if automatic and manifest.kind == "advanced"
            else "manual"
        )
        reason = (
            "系统强制包含四项基础分析"
            if source == "required"
            else f"场景“{scenario.name}”与 {selection.mode} 模式的清单规则"
            if source == "auto"
            else "用户手动选择"
        )
        snapshots.append(
            Snapshot(
                id=skill_id,
                kind=manifest.kind,
                version=manifest.version,
                manifest_checksum=config.manifest_checksum,
                selection_source=source,
                selection_reason=reason,
                config=config.config,
                allowed_tools=list(manifest.allowed_tools),
                requires=list(manifest.requires),
            )
        )
    return Resolution(
        skills=snapshots, auto_selection_strategy="manifest_rules" if automatic else "manual"
    )
