import asyncio
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.security import PASSWORD_HASHER, digest, verify_password
from app.domain.errors import DomainError
from app.domain.schemas import Identity, LoginInput, RegisterInput, TenantView, UserView
from app.infrastructure.auth_repository import AuthRepository
from app.infrastructure.database.accounts import Session, Tenant, TenantMember, User


@dataclass(frozen=True)
class TenantContext:
    session_id: UUID
    csrf_hash: str
    identity: Identity

    @property
    def tenant_id(self) -> UUID:
        return self.identity.tenant.id

    @property
    def user_id(self) -> UUID:
        return self.identity.user.id


@dataclass(frozen=True)
class IssuedSession:
    identity: Identity
    token: str
    csrf: str


def identity_view(user: User, tenant: Tenant, member: TenantMember) -> Identity:
    return Identity(
        user=UserView(id=user.id, email=user.email, display_name=user.display_name),
        tenant=TenantView.model_validate(
            {"id": tenant.id, "name": tenant.name, "role": member.role}
        ),
    )


class AuthService:
    def __init__(self, database: AsyncSession, settings: Settings) -> None:
        self.database = database
        self.settings = settings
        self.repository = AuthRepository(database)

    async def issue(self, user: User, tenant: Tenant, member: TenantMember) -> IssuedSession:
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.database.add(
            Session(
                user_id=user.id,
                token_hash=digest(token),
                csrf_hash=digest(csrf),
                expires_at=datetime.now(UTC) + timedelta(seconds=self.settings.session_ttl_seconds),
            )
        )
        return IssuedSession(identity_view(user, tenant, member), token, csrf)

    async def register(self, payload: RegisterInput) -> IssuedSession:
        password_hash = await asyncio.to_thread(
            PASSWORD_HASHER.hash, payload.password.get_secret_value()
        )
        user = User(
            email=str(payload.email), display_name=payload.display_name, password_hash=password_hash
        )
        self.database.add(user)
        try:
            await self.database.flush()
            tenant = Tenant(
                name=f"{user.display_name}的工作空间", type="personal", created_by=user.id
            )
            self.database.add(tenant)
            await self.database.flush()
            member = TenantMember(
                tenant_id=tenant.id, user_id=user.id, role="owner", status="active"
            )
            self.database.add(member)
            await self.database.flush()
            result = await self.issue(user, tenant, member)
            await self.database.commit()
            return result
        except IntegrityError:
            await self.database.rollback()
            raise DomainError(409, "email_registered", "该邮箱已注册，请登录") from None

    async def login(self, payload: LoginInput) -> IssuedSession:
        user = await self.repository.by_email(str(payload.email))
        valid = await asyncio.to_thread(
            verify_password,
            user.password_hash if user else None,
            payload.password.get_secret_value(),
        )
        if not valid or user is None or user.status != "active":
            raise DomainError(401, "invalid_credentials", "邮箱或密码不正确")
        personal = await self.repository.personal_tenant(user)
        if personal is None:
            raise DomainError(403, "membership_inactive", "工作空间成员关系不可用")
        if PASSWORD_HASHER.check_needs_rehash(user.password_hash):
            user.password_hash = await asyncio.to_thread(
                PASSWORD_HASHER.hash, payload.password.get_secret_value()
            )
        result = await self.issue(user, *personal)
        await self.database.commit()
        return result

    async def resolve(self, token: str | None) -> TenantContext:
        row = (
            await self.repository.session_identity(digest(token))
            if token and len(token) <= 128
            else None
        )
        if row is None:
            raise DomainError(401, "unauthorized", "请先登录")
        session, user, tenant, member = row
        return TenantContext(session.id, session.csrf_hash, identity_view(user, tenant, member))

    async def logout(self, context: TenantContext) -> None:
        session = await self.database.get(Session, context.session_id)
        if session is not None:
            session.revoked_at = datetime.now(UTC)
            await self.database.commit()
