from pathlib import Path

from app.agent.skills.loader import Definition, load_definition
from app.agent.skills.models import ADVANCED_IDS, CORE_IDS, SCENARIO_IDS
from app.agent.skills.validator import validate_registry
from app.domain.errors import DomainError


class SkillRegistry:
    def __init__(self, definitions: list[Definition]) -> None:
        validate_registry(definitions)
        self._definitions = {item.manifest.id: item for item in definitions}

    @classmethod
    def from_directory(cls, root: Path) -> "SkillRegistry":
        return cls(
            [load_definition(path.parent, root) for path in sorted(root.glob("*/manifest.yaml"))]
        )

    def get(self, skill_id: str) -> Definition:
        if skill_id not in self._definitions:
            raise DomainError(404, "skill_not_found", "技能不存在")
        return self._definitions[skill_id]

    def all(self) -> list[Definition]:
        return [self.get(skill_id) for skill_id in (*SCENARIO_IDS, *CORE_IDS, *ADVANCED_IDS)]
