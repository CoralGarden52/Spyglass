import asyncio
import ipaddress
import socket
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser

import httpx

from app.infrastructure.providers.chat import bounded_body


async def validate_url(value: str) -> tuple[httpx.URL, str]:
    try:
        url = httpx.URL(value)
        if (
            url.scheme not in {"http", "https"}
            or not url.host
            or url.username
            or url.password
            or url.port not in {None, 80, 443}
        ):
            raise ValueError("unsafe_url")
        try:
            addresses = [str(ipaddress.ip_address(url.host))]
        except ValueError:
            async with asyncio.timeout(3):
                records = await asyncio.get_running_loop().getaddrinfo(
                    url.host,
                    url.port or (443 if url.scheme == "https" else 80),
                    type=socket.SOCK_STREAM,
                )
            addresses = [str(item[4][0]) for item in records]
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ValueError("unsafe_address")
        return url, addresses[0]
    except (httpx.InvalidURL, OSError, TimeoutError):
        raise ValueError("url_unavailable") from None


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.hidden = 0
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"}:
            self.hidden = max(0, self.hidden - 1)

    def handle_data(self, data: str) -> None:
        if not self.hidden and data.strip():
            self.parts.append(data.strip())


class SafeFetcher:
    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def request(self, value: str, check_robots: bool = False) -> tuple[str, str, int]:
        # Pin the validated IP. Host and TLS SNI keep original hostname validation;
        # DNS is never resolved a second time by the HTTP transport.
        for _ in range(4):
            url, ip = await validate_url(value)
            if check_robots:
                await self.allowed(str(url))
            async with self.client.stream(
                "GET",
                url.copy_with(host=ip),
                headers={"Host": url.host, "User-Agent": "SpyglassBot/0.1"},
                extensions={"sni_hostname": url.host},
                follow_redirects=False,
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    if not check_robots:
                        raise ValueError("robots_redirect_not_supported")
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("invalid_redirect")
                    value = str(url.join(location))
                    continue
                if response.status_code not in {200, 404}:
                    raise ValueError("web_http_error")
                kind = response.headers.get("content-type", "").split(";")[0]
                if kind not in {"text/html", "text/plain", "application/xhtml+xml"}:
                    raise ValueError("unsupported_media")
                data = await bounded_body(response, 1_000_000)
                return data.decode("utf-8", errors="replace"), str(url), response.status_code
        raise ValueError("redirect_limit")

    async def fetch(self, value: str) -> dict[str, str]:
        async with asyncio.timeout(15):
            html, canonical, status = await self.request(value, check_robots=True)
            if status != 200:
                raise ValueError("page_not_found")
            extractor = TextExtractor()
            extractor.feed(html)
            return {"url": canonical, "text": "\n".join(extractor.parts)[:14000]}

    async def allowed(self, value: str) -> None:
        url, _ = await validate_url(value)
        robots_url = str(url.copy_with(path="/robots.txt", query=None, fragment=None))
        robots, _, status = await self.request(robots_url)
        parser = RobotFileParser()
        parser.parse(robots.splitlines() if status == 200 else [])
        if status == 200 and not parser.can_fetch("SpyglassBot", value):
            raise ValueError("robots_disallowed")
