"""A shared chat quota for JSON and SSE, keyed by authenticated user."""

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


def user_key(request: Request) -> str:
    user_id = getattr(request.state, "user_id", None)
    return str(user_id) if user_id is not None else get_remote_address(request)


limiter = Limiter(key_func=user_key, storage_uri="memory://")


async def rate_limit_error(request: Request, error: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "rate_limit_exceeded",
                "message": "Chat is limited to 5 requests per minute. Please retry shortly.",
            }
        },
        headers={"Retry-After": "60"},
    )
