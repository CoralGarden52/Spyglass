"""Opt-in live API smoke check. Reads keys locally; never prints headers or raw errors.

This diagnostic is not the application's ModelProvider/Tool implementation.
It makes one paid request per configured provider and writes only safe metadata.
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any

import httpx
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


async def check(
    client: httpx.AsyncClient, name: str, url: str, key: str, payload: dict[str, Any]
) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {"provider": name, "ok": False}
    try:
        async with asyncio.timeout(65):
            response = await client.post(
                url,
                headers={"Authorization": f"Bearer {key}"},
                json=payload,
            )
        result["http_status"] = response.status_code
        if response.status_code != 200:
            result["failure"] = "upstream_http_error"
            return result
        try:
            if "text/event-stream" in response.headers.get("content-type", ""):
                content = ""
                usage = None
                returned_model = None
                finish_reason = None
                for line in response.text.splitlines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    frame = json.loads(data)
                    returned_model = frame.get("model") or returned_model
                    usage = frame.get("usage") or usage
                    for choice in frame.get("choices", []):
                        content += (choice.get("delta") or {}).get("content") or ""
                        finish_reason = choice.get("finish_reason") or finish_reason
                body = {
                    "choices": [{"message": {"content": content}, "finish_reason": finish_reason}],
                    "usage": usage,
                    "model": returned_model,
                }
                result["response_format"] = "sse"
            else:
                body = response.json()
                result["response_format"] = "json"
        except ValueError:
            result["failure"] = "non_json_response"
            return result
        if name == "BOCHA":
            data = body.get("data") or {}
            pages = (data.get("webPages") or {}).get("value") or []
            result["ok"] = body.get("code") in (200, "200") and bool(pages)
            result["result_count"] = len(pages)
            result["has_source_urls"] = bool(pages) and all(page.get("url") for page in pages)
            if not result["ok"]:
                result["failure"] = "no_search_results_or_provider_error"
        else:
            choices = body.get("choices") or []
            message = choices[0].get("message", {}) if choices else {}
            content = message.get("content")
            result["ok"] = isinstance(content, str) and bool(content.strip())
            result["has_content"] = bool(content)
            result["finish_reason"] = choices[0].get("finish_reason") if choices else None
            result["usage"] = body.get("usage")
            result["requested_model"] = payload["model"]
            result["returned_model"] = body.get("model")
            if not result["ok"]:
                result["failure"] = "empty_content"
    except TimeoutError:
        result["failure"] = "total_timeout"
    except httpx.HTTPError as exc:
        result["failure"] = type(exc).__name__
    except Exception as exc:
        result["failure"] = type(exc).__name__
    finally:
        result["elapsed_seconds"] = round(time.perf_counter() - started, 2)
    return result


async def main() -> None:
    values = dotenv_values(ROOT / ".env")
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(55, connect=10), follow_redirects=False, trust_env=False
    ) as client:
        calls = []
        for variable, value in values.items():
            if not variable.endswith("_API_KEY") or not value:
                continue
            prefix = variable.removesuffix("_API_KEY")
            base = (values.get(f"{prefix}_BASE_URL") or "").rstrip("/")
            if prefix == "BOCHA":
                endpoint = values.get("BOCHA_WEB_SEARCH_ENDPOINT") or f"{base}/v1/web-search"
                if not endpoint.startswith("https://"):
                    endpoint = f"{base}/{endpoint.lstrip('/')}"
                payload: dict[str, Any] = {
                    "query": "Python programming language official website",
                    "count": 1,
                    "summary": False,
                    "freshness": "noLimit",
                }
            else:
                endpoint = f"{base}/chat/completions"
                payload = {
                    "model": values.get(f"{prefix}_MODEL"),
                    "messages": [{"role": "user", "content": "Reply with exactly OK."}],
                    "max_tokens": 32,
                    "stream": True,
                    "stream_options": {"include_usage": True},
                }
            calls.append(check(client, prefix, endpoint, value, payload))
        results = await asyncio.gather(*calls)
    output = {"kind": "live_provider_smoke_check", "results": results}
    artifact = ROOT / ".artifacts/provider-check.json"
    artifact.parent.mkdir(exist_ok=True)
    artifact.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(output, ensure_ascii=False, indent=2))
    if not results or not all(result["ok"] for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
