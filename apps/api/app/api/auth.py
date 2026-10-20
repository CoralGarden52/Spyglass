from fastapi import APIRouter, Depends, Request, Response

from app.application.auth import AuthService, IssuedSession
from app.core.dependencies import Context, Database, WriteContext, auth_limit, require_origin
from app.domain.schemas import Identity, LoginInput, RegisterInput

router = APIRouter(prefix="/api/v1", tags=["auth"])


def set_session(response: Response, request: Request, result: IssuedSession) -> Identity:
    secure = request.app.state.settings.session_cookie_secure
    ttl = request.app.state.settings.session_ttl_seconds
    response.set_cookie(
        "sg_session",
        result.token,
        max_age=ttl,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        "sg_csrf",
        result.csrf,
        max_age=ttl,
        httponly=False,
        secure=secure,
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"
    return result.identity


@router.post(
    "/auth/register",
    status_code=201,
    response_model=Identity,
    dependencies=[Depends(require_origin), Depends(auth_limit)],
)
async def register(
    payload: RegisterInput, request: Request, response: Response, db: Database
) -> Identity:
    result = await AuthService(db, request.app.state.settings).register(payload)
    return set_session(response, request, result)


@router.post(
    "/auth/login",
    response_model=Identity,
    dependencies=[Depends(require_origin), Depends(auth_limit)],
)
async def login(
    payload: LoginInput, request: Request, response: Response, db: Database
) -> Identity:
    result = await AuthService(db, request.app.state.settings).login(payload)
    return set_session(response, request, result)


@router.post("/auth/logout", status_code=204)
async def logout(request: Request, response: Response, db: Database, context: WriteContext) -> None:
    await AuthService(db, request.app.state.settings).logout(context)
    for name in ["sg_session", "sg_csrf"]:
        response.delete_cookie(
            name,
            path="/",
            secure=request.app.state.settings.session_cookie_secure,
            httponly=name == "sg_session",
            samesite="lax" if name == "sg_session" else "strict",
        )


@router.get("/users/me", response_model=Identity)
async def me(context: Context, response: Response) -> Identity:
    response.headers["Cache-Control"] = "no-store"
    return context.identity
