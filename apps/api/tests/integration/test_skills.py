from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

pytestmark = pytest.mark.integration
CORE = {"product_capability", "pricing_analysis", "user_sentiment", "swot_analysis"}


def test_config_retry_ignores_json_object_key_order(api_client: TestClient) -> None:
    register(api_client)
    key = str(uuid4())
    first = api_client.patch(
        "/api/v1/skills/product_capability/config",
        json={"expected_revision": 0, "config": {"max_findings": 12, "evidence_quote_limit": 4}},
        headers=headers(api_client, key),
    )
    retry = api_client.patch(
        "/api/v1/skills/product_capability/config",
        json={"config": {"evidence_quote_limit": 4, "max_findings": 12}, "expected_revision": 0},
        headers=headers(api_client, key),
    )
    assert first.status_code == 200
    assert retry.status_code == 200
    assert first.json() == retry.json()


def register(client: TestClient, email: str = "skills@example.com") -> None:
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "Skill-test-passphrase-42", "display_name": "技能研究员"},
    )
    assert response.status_code == 201


def headers(client: TestClient, key: str | None = None) -> dict[str, str]:
    return {"X-CSRF-Token": client.cookies["sg_csrf"], "Idempotency-Key": key or str(uuid4())}


def test_registry_exposes_thirteen_validated_skills(api_client: TestClient) -> None:
    register(api_client)
    response = api_client.get("/api/v1/skills")
    assert response.status_code == 200
    rows = response.json()["data"]
    assert len(rows) == 13
    assert {
        kind: sum(row["kind"] == kind for row in rows) for kind in ["scenario", "core", "advanced"]
    } == {"scenario": 6, "core": 4, "advanced": 3}
    detail = api_client.get("/api/v1/skills/user_sentiment").json()["data"]
    assert detail["version"] == "0.1.0"
    assert len(detail["manifest_checksum"]) == 64
    assert "mixed" in detail["instructions"]
    assert detail["output_json_schema"]["properties"]
    assert detail["is_system_required"] is True


def test_resolution_always_includes_core_and_only_one_scenario(api_client: TestClient) -> None:
    register(api_client)
    for mode in ["quick", "standard", "deep"]:
        response = api_client.post(
            "/api/v1/skills/resolve",
            json={
                "mode": mode,
                "scenario_skill_id": "ai_llm",
                "advanced_skill_ids": ["market_landscape"],
                "advanced_skill_selection": "manual",
            },
            headers=headers(api_client),
        )
        assert response.status_code == 200
        plan = response.json()["data"]
        assert {item["id"] for item in plan["skills"] if item["kind"] == "core"} == CORE
        assert [item["id"] for item in plan["skills"] if item["kind"] == "scenario"] == ["ai_llm"]
        assert [item["id"] for item in plan["skills"] if item["kind"] == "advanced"] == [
            "market_landscape"
        ]
    for payload in [
        {"scenario_skill_id": ["ai_llm", "finance"]},
        {"core_skill_ids": []},
        {"advanced_skill_ids": ["swot_analysis"]},
    ]:
        assert (
            api_client.post(
                "/api/v1/skills/resolve", json=payload, headers=headers(api_client)
            ).status_code
            == 422
        )


def test_core_disable_and_unknown_config_are_rejected(api_client: TestClient) -> None:
    register(api_client)
    for skill in CORE:
        response = api_client.patch(
            f"/api/v1/skills/{skill}/config",
            json={"enabled": False, "expected_revision": 0},
            headers=headers(api_client),
        )
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "required_skill"
    response = api_client.patch(
        "/api/v1/skills/user_sentiment/config",
        json={"config": {"api_key": "forbidden"}, "expected_revision": 0},
        headers=headers(api_client),
    )
    assert response.status_code == 422
    assert "forbidden" not in response.text


def test_config_is_tenant_isolated_idempotent_and_revisioned(api_client: TestClient) -> None:
    register(api_client)
    key = str(uuid4())
    payload = {"enabled": False, "expected_revision": 0}
    response = api_client.patch(
        "/api/v1/skills/market_landscape/config", json=payload, headers=headers(api_client, key)
    )
    assert response.status_code == 200
    assert response.json()["data"]["revision"] == 1
    assert response.json()["data"]["enabled"] is False
    replay = api_client.patch(
        "/api/v1/skills/market_landscape/config", json=payload, headers=headers(api_client, key)
    )
    assert replay.json() == response.json()
    assert (
        api_client.patch(
            "/api/v1/skills/market_landscape/config",
            json={"enabled": True, "expected_revision": 0},
            headers=headers(api_client, key),
        ).status_code
        == 409
    )
    assert (
        api_client.patch(
            "/api/v1/skills/market_landscape/config",
            json={"enabled": True, "expected_revision": 0},
            headers=headers(api_client),
        ).status_code
        == 409
    )
    assert (
        api_client.post(
            "/api/v1/skills/resolve",
            json={"advanced_skill_ids": ["market_landscape"]},
            headers=headers(api_client),
        ).status_code
        == 409
    )
    api_client.post("/api/v1/auth/logout", headers=headers(api_client))
    register(api_client, "other-skills@example.com")
    assert api_client.get("/api/v1/skills/market_landscape").json()["data"]["enabled"] is True
    assert api_client.get("/api/v1/skills/market_landscape").json()["data"]["revision"] == 0


def test_skills_endpoints_require_authentication_and_write_security(api_client: TestClient) -> None:
    assert api_client.get("/api/v1/skills").status_code == 401
    register(api_client)
    assert (
        api_client.patch(
            "/api/v1/skills/market_landscape/config",
            json={"enabled": False, "expected_revision": 0},
        ).status_code
        == 403
    )
    assert api_client.get("/api/v1/skills/not-a-skill").status_code == 404
    assert (
        api_client.patch(
            "/api/v1/skills/market_landscape/config",
            json={"enabled": False, "expected_revision": 0, "tenant_id": str(uuid4())},
            headers=headers(api_client),
        ).status_code
        == 422
    )
