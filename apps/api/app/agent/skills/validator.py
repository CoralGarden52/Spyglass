from app.agent.skills.loader import Definition, SkillValidationError
from app.agent.skills.models import ADVANCED_IDS, CORE_IDS, SCENARIO_IDS


def validate_registry(definitions: list[Definition]) -> None:
    by_id = {item.manifest.id: item for item in definitions}
    if len(by_id) != len(definitions):
        raise SkillValidationError("Duplicate skill IDs")
    expected = {
        **dict.fromkeys(SCENARIO_IDS, "scenario"),
        **dict.fromkeys(CORE_IDS, "core"),
        **dict.fromkeys(ADVANCED_IDS, "advanced"),
    }
    if set(by_id) != set(expected) or any(
        item.manifest.kind != expected[item.manifest.id] for item in definitions
    ):
        raise SkillValidationError(
            "Registry must contain exactly six scenarios, four core and three advanced"
        )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(skill_id: str) -> None:
        if skill_id in visiting:
            raise SkillValidationError("Cyclic skill dependencies")
        if skill_id in visited:
            return
        visiting.add(skill_id)
        for dependency in by_id[skill_id].manifest.requires:
            if dependency == "normalized_evidence":
                continue
            if dependency not in by_id:
                raise SkillValidationError("Unknown skill dependency")
            visit(dependency)
        visiting.remove(skill_id)
        visited.add(skill_id)

    for skill_id in by_id:
        visit(skill_id)
