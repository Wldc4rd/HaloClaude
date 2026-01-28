"""
MCP Authentication Middleware

Validates API key for MCP endpoint access.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import get_settings


class MCPAuthMiddleware(BaseHTTPMiddleware):
    """Middleware to authenticate MCP requests using API key."""

    async def dispatch(self, request: Request, call_next):
        # Only apply to /mcp paths
        if request.url.path.startswith("/mcp"):
            settings = get_settings()

            # Check Authorization header (Bearer token) or api-key header
            auth_header = request.headers.get("authorization", "")
            api_key_header = request.headers.get("api-key", "")

            valid = False
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                valid = token == settings.litellm_master_key
            elif api_key_header:
                valid = api_key_header == settings.litellm_master_key

            if not valid:
                return JSONResponse(
                    status_code=401,
                    content={
                        "jsonrpc": "2.0",
                        "error": {
                            "code": -32001,
                            "message": "Unauthorized: Invalid or missing API key",
                        },
                        "id": None,
                    },
                )

        return await call_next(request)
