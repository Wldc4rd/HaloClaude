"""
MCP Authentication

Provides two auth strategies:
1. EntraTokenVerifier — validates Entra ID JWTs OR static LITELLM_MASTER_KEY
   (used when ENTRA_TENANT_ID + ENTRA_CLIENT_ID are configured)
2. MCPAuthMiddleware — legacy static-key-only middleware
   (used when Entra ID is NOT configured)
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Entra ID JWT + static-key dual verifier (MCP TokenVerifier protocol)
# ---------------------------------------------------------------------------

class EntraTokenVerifier:
    """
    Validates Bearer tokens for the MCP endpoint.

    Accepts EITHER:
      1. An Azure Entra ID JWT (validated against JWKS, audience, issuer)
      2. The static LITELLM_MASTER_KEY (for backward compat with Claude Desktop)

    Implements the TokenVerifier protocol expected by FastMCP.
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        static_key: str,
    ):
        import jwt
        from jwt import PyJWKClient

        self.tenant_id = tenant_id
        self.client_id = client_id
        self.static_key = static_key
        # Entra ID may issue v1 or v2 tokens depending on app config
        self.valid_issuers = [
            f"https://login.microsoftonline.com/{tenant_id}/v2.0",
            f"https://sts.windows.net/{tenant_id}/",
        ]
        # Use the common Microsoft JWKS endpoint (covers both v1 and v2 tokens)
        self.jwks_uri = "https://login.microsoftonline.com/common/discovery/v2.0/keys"
        # Entra ID sets aud to api://<client_id> when resource scopes are used,
        # or bare <client_id> when only openid/profile scopes are used.
        self.valid_audiences = [client_id, f"api://{client_id}"]
        self._jwt = jwt
        self._jwks_client = PyJWKClient(self.jwks_uri, cache_jwk_set=True, lifespan=300)

    async def verify_token(self, token: str):
        """Verify a bearer token. Returns AccessToken if valid, None otherwise."""
        from mcp.server.auth.provider import AccessToken

        # Fast path: check static key
        if token == self.static_key:
            return AccessToken(
                token=token,
                client_id="static-key",
                scopes=[],
                expires_at=None,
            )

        # Try Entra ID JWT validation
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            payload = self._jwt.decode(
                token,
                signing_key.key,
                algorithms=["RS256"],
                audience=self.valid_audiences,
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": False,  # verify manually (v1 vs v2)
                },
            )

            # Verify issuer manually (Entra v1 and v2 use different formats)
            token_issuer = payload.get("iss", "")
            if token_issuer not in self.valid_issuers:
                logger.warning(f"MCP auth: JWT issuer mismatch: {token_issuer}")
                return None

            return AccessToken(
                token=token,
                client_id=payload.get("sub", payload.get("oid", "unknown")),
                scopes=payload.get("scp", "").split() if payload.get("scp") else [],
                expires_at=payload.get("exp"),
            )

        except self._jwt.ExpiredSignatureError:
            logger.warning("MCP auth: JWT has expired")
            return None
        except self._jwt.InvalidAudienceError:
            logger.warning("MCP auth: JWT audience mismatch")
            return None
        except self._jwt.InvalidIssuerError:
            logger.warning("MCP auth: JWT issuer mismatch")
            return None
        except self._jwt.PyJWTError as e:
            logger.warning(f"MCP auth: JWT validation failed: {e}")
            return None
        except Exception as e:
            logger.error(f"MCP auth: Unexpected error during token validation: {e}")
            return None


# ---------------------------------------------------------------------------
# api-key header normalisation middleware
# ---------------------------------------------------------------------------

class ApiKeyHeaderMiddleware(BaseHTTPMiddleware):
    """Normalize api-key header to Authorization: Bearer for /mcp paths.

    When Entra ID auth is active, the MCP library's BearerAuthBackend only
    reads the Authorization header.  Claude Desktop sends api-key instead,
    so this middleware copies it across.
    """

    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith("/mcp"):
            api_key = request.headers.get("api-key", "")
            auth_header = request.headers.get("authorization", "")
            if api_key and not auth_header:
                # Rebuild headers list with Authorization added
                raw_headers = list(request.scope["headers"])
                raw_headers.append(
                    (b"authorization", f"Bearer {api_key}".encode())
                )
                request.scope["headers"] = raw_headers

        return await call_next(request)


# ---------------------------------------------------------------------------
# Legacy static-key middleware (used when Entra ID is NOT configured)
# ---------------------------------------------------------------------------

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
