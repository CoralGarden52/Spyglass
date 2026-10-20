from fastapi import APIRouter, Request, Response

from app.application.health import LivenessResponse, ReadinessResponse, get_readiness

router = APIRouter(prefix="/api/v1/health", tags=["system"])


@router.get("/live", response_model=LivenessResponse)
async def live() -> LivenessResponse:
    """Public process probe; contains no tenant data and does not call AI providers."""
    return LivenessResponse()


@router.get(
    "/ready", response_model=ReadinessResponse, responses={503: {"model": ReadinessResponse}}
)
async def ready(request: Request, response: Response) -> ReadinessResponse:
    """Public dependency readiness; provider status means configuration only, not a network test."""
    result = await get_readiness(request.app.state.resources, request.app.state.settings)
    if result.status != "ready":
        response.status_code = 503
    response.headers["Cache-Control"] = "no-store"
    return result
