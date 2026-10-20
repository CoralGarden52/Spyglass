from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database.accounts import Session, Tenant, TenantMember, User


class AuthRepository:
    def __init__(self, database: AsyncSession) -> None:
        self.database = database

    async def by_email(self, email: str) -> User | None:
        return cast(
            User | None, await self.database.scalar(select(User).where(User.email == email))
        )

    async def session_identity(
        self, token_hash: str
    ) -> tuple[Session, User, Tenant, TenantMember] | None:
        row = (
            await self.database.execute(
                select(Session, User, Tenant, TenantMember)
                .join(User, User.id == Session.user_id)
                .join(TenantMember, TenantMember.user_id == User.id)
                .join(Tenant, Tenant.id == TenantMember.tenant_id)
                .where(
                    Session.token_hash == token_hash,
                    Session.revoked_at.is_(None),
                    Session.expires_at > datetime.now(UTC),
                    User.status == "active",
                    TenantMember.status == "active",
                    Tenant.type == "personal",
                    Tenant.created_by == User.id,
                )
            )
        ).one_or_none()
        return (row[0], row[1], row[2], row[3]) if row else None

    async def personal_tenant(self, user: User) -> tuple[Tenant, TenantMember] | None:
        row = (
            await self.database.execute(
                select(Tenant, TenantMember)
                .join(TenantMember, TenantMember.tenant_id == Tenant.id)
                .where(
                    Tenant.created_by == user.id,
                    Tenant.type == "personal",
                    TenantMember.user_id == user.id,
                    TenantMember.status == "active",
                )
            )
        ).one_or_none()
        return (row[0], row[1]) if row else None
