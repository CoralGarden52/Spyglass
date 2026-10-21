import asyncio
from datetime import UTC, datetime
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, ValidationError
from pydantic import BaseModel
from pydantic import ValidationError as ModelValidationError

from app.agent.runtime.contracts import ModelInput, ModelProvider, Role
from app.agent.runtime.evidence_context import evidence_context
from app.agent.skills.contracts import SCHEMAS
from app.agent.tools.registry import ToolRegistry
from app.infrastructure.providers.chat import ProviderError
from app.infrastructure.research_store import ResearchStore, digest


class NodeContext:
    def __init__(
        self,
        store: ResearchStore,
        model: ModelProvider,
        tools: ToolRegistry,
        definitions: dict[str, dict[str, Any]],
    ):
        self.store, self.model, self.tools, self.definitions = store, model, tools, definitions

    async def call(
        self,
        role: Role,
        instructions: str,
        context: dict[str, Any],
        schema: type[BaseModel] | dict[str, Any],
        version: str = "research-v1",
    ) -> dict[str, Any]:
        context = {"as_of_utc": datetime.now(UTC).date().isoformat(), **context}
        if isinstance(context.get("untrusted_evidence"), list):
            context = {
                **context,
                "untrusted_evidence": evidence_context(context["untrusted_evidence"], role),
            }
        document = schema.model_json_schema() if isinstance(schema, type) else schema
        started = datetime.now(UTC)
        model, usage, output_hash, error = None, None, None, None
        try:
            reply = await self.model.generate(
                ModelInput(
                    role=role,
                    instructions=instructions,
                    context=context,
                    output_schema=document,
                    prompt_version=version,
                )
            )
            model, usage = reply.model, reply.usage
            Draft202012Validator(document, format_checker=FormatChecker()).validate(reply.data)
            validate_fact_policy(reply.data)
            contract = (
                schema if isinstance(schema, type) else SCHEMAS.get(document.get("title", ""))
            )
            if contract is not None and contract.model_json_schema() == document:
                contract.model_validate(reply.data)
            output_hash = digest(reply.data)
            return reply.data
        except (ValidationError, ModelValidationError) as exc:
            import re

            path = (
                exc.json_path if isinstance(exc, ValidationError) else str(exc.errors()[0]["loc"])
            )
            error = "schema_error:" + re.sub(r"[^A-Za-z0-9_.$\[\]]", "_", path)[:65]
            raise ProviderError(error) from None
        except ProviderError as exc:
            error = str(exc)
            model = getattr(exc, "model", None) or model
            usage = getattr(exc, "usage", None) or usage
            raise
        except asyncio.CancelledError:
            error = "cancelled"
            raise
        finally:
            await self.store.audit(
                kind="model",
                name=role,
                prompt_version=version,
                input_hash=digest(context),
                output_hash=output_hash,
                model=model,
                usage_json=usage,
                status="failed" if error else "completed",
                error_code=error,
                started_at=started,
                ended_at=datetime.now(UTC),
            )

    async def tool(self, name: str, args: dict[str, Any], skill_id: str) -> list[dict[str, Any]]:
        started = datetime.now(UTC)
        result, error = None, None
        call_id = await self.store.events.start_tool(name, args)
        try:
            result = await self.tools.execute(
                name,
                args,
                self.definitions[skill_id]["allowed_tools"],
                await self.store.evidence()
                if name in {"evidence_search", "knowledge_retrieval"}
                else None,
            )
            return result
        except asyncio.CancelledError:
            error = "cancelled"
            raise
        except Exception as exc:
            error = str(exc) if isinstance(exc, ProviderError) else "tool_rejected"
            raise ProviderError(error) from None
        finally:
            await self.store.events.finish_tool(
                call_id, name, len(result) if result is not None else None, error
            )
            await self.store.audit(
                kind="tool",
                name=name,
                prompt_version=None,
                input_hash=digest(args),
                output_hash=digest(result) if result is not None else None,
                model=None,
                usage_json=None,
                status="failed" if error else "completed",
                error_code=error,
                started_at=started,
                ended_at=datetime.now(UTC),
            )


def empty_analysis(schema: dict[str, Any], reason: str) -> dict[str, Any]:
    value: dict[str, Any] = {
        "schema_version": 1,
        "status": "insufficient_evidence",
        "limitations": [reason],
    }
    for key, field in schema.get("properties", {}).items():
        if key not in value and field.get("type") == "array":
            value[key] = [reason] if key == "sampling_bias" else []
    Draft202012Validator(schema).validate(value)
    return value


def validate_fact_policy(value: Any) -> None:
    """Version-independent grounding/safety floor, including historical schemas."""
    if isinstance(value, dict):
        if value.get("evidence_status") in {"supported", "partial"} and not value.get(
            "evidence_ids"
        ):
            raise ProviderError("missing_evidence")
        if value.get("amount") is not None:
            import re

            if (
                not re.fullmatch("[A-Z]{3}", str(value.get("currency", "")))
                or not str(value.get("billing_unit") or "").strip()
            ):
                raise ProviderError("schema_error")
        for child in value.values():
            validate_fact_policy(child)
    elif isinstance(value, list):
        for child in value:
            validate_fact_policy(child)
