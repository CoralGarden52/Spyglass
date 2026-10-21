"""Opt-in PAID public API research check. Stores real results in the signed-in tenant."""

import argparse
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password-env", default="SPYGLASS_CHECK_PASSWORD")
    parser.add_argument("--message", required=True)
    parser.add_argument("--scenario", default="general_analysis")
    parser.add_argument("--mode", default="standard")
    parser.add_argument("--advanced", action="append", default=[])
    args = parser.parse_args()
    password = os.environ.get(args.password_env)
    if not password:
        raise SystemExit("Set the requested password environment variable locally")
    started = time.monotonic()
    with httpx.Client(
        base_url=args.base_url, timeout=30, trust_env=False, headers={"Origin": args.base_url}
    ) as client:
        login = client.post("/api/v1/auth/login", json={"email": args.email, "password": password})
        if login.status_code != 200:
            raise SystemExit(f"Login failed: HTTP {login.status_code}")

        def write(path: str, body: dict) -> dict:
            response = client.post(
                "/api/v1" + path,
                json=body,
                headers={
                    "X-CSRF-Token": client.cookies["sg_csrf"],
                    "Idempotency-Key": str(uuid4()),
                },
            )
            if response.status_code not in {200, 201}:
                raise SystemExit(f"API failed: HTTP {response.status_code} at {path}")
            return response.json()

        project = write(
            "/research",
            {
                "title": "真实联网验收：" + args.message[:100],
                "mode": args.mode,
                "scenario_skill_id": args.scenario,
            },
        )["data"]
        thread = write("/threads", {"project_id": project["id"], "title": "真实联网验收"})["data"]
        run = write(
            f"/threads/{thread['id']}/runs",
            {
                "user_message": args.message,
                "mode": args.mode,
                "scenario_skill_id": args.scenario,
                "advanced_skill_ids": args.advanced,
                "advanced_skill_selection": "manual",
            },
        )["data"]
        print(
            json.dumps(
                {"run_id": run["id"], "thread_url": args.base_url + "/threads/" + thread["id"]}
            ),
            flush=True,
        )
        events: list[dict] = []
        after = 0
        while time.monotonic() - started < 360:
            response = client.get(f"/api/v1/runs/{run['id']}")
            response.raise_for_status()
            run = response.json()["data"]
            batch = client.get(
                f"/api/v1/runs/{run['id']}/events/history",
                params={"after_seq": after, "limit": 500},
            )
            batch.raise_for_status()
            rows = batch.json()["data"]
            if rows:
                events.extend(rows)
                after = rows[-1]["seq"]
                print(
                    json.dumps(
                        {
                            "elapsed": round(time.monotonic() - started, 1),
                            "status": run["status"],
                            "last_event": rows[-1]["type"],
                            "event_count": len(events),
                        },
                        ensure_ascii=True,
                    ),
                    flush=True,
                )
            if run["status"] in {"completed", "needs_review", "failed", "cancelled"}:
                break
            time.sleep(2)
        else:
            raise SystemExit("Live check deadline reached; run remains queryable in the website")
        report = None
        if run["report_id"]:
            response = client.get(f"/api/v1/reports/{run['report_id']}")
            response.raise_for_status()
            report = response.json()["data"]
        messages = client.get(f"/api/v1/threads/{thread['id']}/messages").json()["data"]
        result = {
            "kind": "paid_live_public_run",
            "run": run,
            "report": report,
            "messages": messages,
            "events": events,
            "elapsed_seconds": round(time.monotonic() - started, 2),
        }
        root = Path(__file__).resolve().parents[1]
        artifact = (
            root
            / ".artifacts"
            / ("slice4-live-run-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + ".json")
        )
        artifact.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    "artifact": artifact.name,
                    "status": run["status"],
                    "elapsed_seconds": result["elapsed_seconds"],
                    "report_id": run["report_id"],
                    "sections": len(report["content"]["sections"]) if report else 0,
                    "claims": sum(len(s["claims"]) for s in report["content"]["sections"])
                    if report
                    else 0,
                    "error_code": run["error_code"],
                }
            ),
            flush=True,
        )
        if run["status"] != "completed":
            raise SystemExit(1)


if __name__ == "__main__":
    main()
