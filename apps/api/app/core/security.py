import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError

PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=2)
DUMMY_HASH = PASSWORD_HASHER.hash(secrets.token_urlsafe(32))


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def matches(token: str, expected_digest: str) -> bool:
    return hmac.compare_digest(digest(token), expected_digest)


def verify_password(password_hash: str | None, password: str) -> bool:
    try:
        valid = PASSWORD_HASHER.verify(password_hash or DUMMY_HASH, password)
        return bool(password_hash) and valid
    except VerificationError:
        return False
