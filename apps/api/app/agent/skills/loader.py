import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from app.agent.skills.contracts import SCHEMAS, AnalysisConfig, ScenarioConfig, schema_document
from app.agent.skills.models import TOOL_WHITELIST, Manifest


class SkillValidationError(ValueError):
    """Definition rejected before it receives execution privileges."""


@dataclass(frozen=True)
class Definition:
    manifest: Manifest
    instructions: str
    checksum: str


def load_definition(directory: Path, root: Path) -> Definition:
    try:
        manifest_path = (directory / "manifest.yaml").resolve(strict=True)
        entrypoint = (directory / "SKILL.md").resolve(strict=True)
        if (
            not directory.resolve().is_relative_to(root.resolve())
            or not manifest_path.is_relative_to(directory.resolve())
            or not entrypoint.is_relative_to(directory.resolve())
        ):
            raise SkillValidationError("Skill files must remain inside their definition directory")
        if manifest_path.stat().st_size > 65536 or entrypoint.stat().st_size > 65536:
            raise SkillValidationError("Skill files exceed size limit")
        raw = manifest_path.read_bytes()
        if any(isinstance(token, yaml.tokens.AliasToken) for token in yaml.scan(raw)):
            raise SkillValidationError("YAML aliases are not supported")
        manifest = Manifest.model_validate(yaml.safe_load(raw))
        if manifest.id != directory.name:
            raise SkillValidationError("Skill ID must match directory name")
        if not set(manifest.allowed_tools) <= TOOL_WHITELIST:
            raise SkillValidationError("Declared tool is outside the whitelist")
        if any(
            name not in SCHEMAS
            for name in (manifest.input_schema, manifest.output_schema, manifest.config_schema)
        ):
            raise SkillValidationError("Unknown schema contract")
        if not issubclass(SCHEMAS[manifest.config_schema], (ScenarioConfig, AnalysisConfig)):
            raise SkillValidationError("Config schema must declare validated default parameters")
        instructions_bytes = entrypoint.read_bytes()
        instructions = instructions_bytes.decode("utf-8")
        if len(instructions.strip()) < 80:
            raise SkillValidationError("Skill guidance is incomplete")
        schemas = [
            schema_document(name)
            for name in (manifest.input_schema, manifest.output_schema, manifest.config_schema)
        ]
        checksum = hashlib.sha256(
            raw
            + b"\0"
            + instructions_bytes
            + b"\0"
            + json.dumps(schemas, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        return Definition(manifest, instructions, checksum)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        if isinstance(exc, SkillValidationError):
            raise
        raise SkillValidationError(f"Invalid skill definition in {directory.name}") from None
