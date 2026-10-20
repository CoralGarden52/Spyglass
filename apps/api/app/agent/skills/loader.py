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
    legacy_checksums: frozenset[str] = frozenset()


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
        original_manifest = manifest_path.read_bytes()
        raw = original_manifest.replace(b"\r\n", b"\n")
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
        original_instructions = entrypoint.read_bytes()
        instructions_bytes = original_instructions.replace(b"\r\n", b"\n")
        instructions = instructions_bytes.decode("utf-8")
        if len(instructions.strip()) < 80:
            raise SkillValidationError("Skill guidance is incomplete")
        schemas = [
            schema_document(name)
            for name in (manifest.input_schema, manifest.output_schema, manifest.config_schema)
        ]
        schema_bytes = json.dumps(schemas, sort_keys=True, ensure_ascii=False).encode()

        def content_hash(manifest_bytes: bytes, guidance_bytes: bytes) -> str:
            return hashlib.sha256(
                manifest_bytes + b"\0" + guidance_bytes + b"\0" + schema_bytes
            ).hexdigest()

        checksum = content_hash(raw, instructions_bytes)
        # Older releases hashed raw files. Accept only known LF/CRLF variants of
        # these exact files and schemas; substantive edits still require a new version.
        legacy_checksums = frozenset(
            {
                content_hash(manifest_variant, guidance_variant)
                for manifest_variant in (raw, raw.replace(b"\n", b"\r\n"))
                for guidance_variant in (
                    instructions_bytes,
                    instructions_bytes.replace(b"\n", b"\r\n"),
                )
            }
            | {content_hash(original_manifest, original_instructions)}
        )
        return Definition(manifest, instructions, checksum, legacy_checksums)
    except (OSError, UnicodeError, ValueError, yaml.YAMLError) as exc:
        if isinstance(exc, SkillValidationError):
            raise
        raise SkillValidationError(f"Invalid skill definition in {directory.name}") from None
