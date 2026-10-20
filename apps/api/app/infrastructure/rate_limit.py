import hashlib
from collections.abc import Awaitable
from typing import cast

from redis.asyncio import Redis
from redis.exceptions import RedisError

from app.core.config import Settings
from app.domain.errors import DomainError

COUNTER_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
return count
"""


async def check_auth_limit(redis: Redis, settings: Settings, action: str, subject: str) -> None:
    fingerprint = hashlib.sha256(subject.encode()).hexdigest()
    key = f"{settings.rate_limit_namespace}:auth:{action}:{fingerprint}"
    try:
        count = await cast(
            Awaitable[int],
            redis.eval(COUNTER_SCRIPT, 1, key, str(settings.auth_rate_window_seconds)),
        )
    except RedisError:
        raise DomainError(
            503, "auth_temporarily_unavailable", "登录服务暂时不可用，请稍后重试"
        ) from None
    if int(count) > settings.auth_rate_limit:
        raise DomainError(
            429,
            "rate_limited",
            "请求过于频繁，请稍后重试",
            headers={"Retry-After": str(settings.auth_rate_window_seconds)},
        )
