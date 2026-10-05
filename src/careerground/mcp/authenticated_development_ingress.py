"""Loopback-only product MCP listener for an already configured private tunnel.

Shares the authenticated Web app's resource server and DB. It never serves Web
routes, accepts browser cookies as authentication, or creates tunnel resources.
Its server runs without a second lifespan; the Web listener owns MCP startup.
"""

from urllib.parse import urlsplit

from starlette.responses import Response


class AuthenticatedDevelopmentMcpIngress:
    def __init__(self, management, resource_url: str):
        self.app = management.mcp
        path = urlsplit(resource_url).path
        self.paths = {
            "/mcp",
            "/.well-known/oauth-protected-resource",
            "/.well-known/oauth-protected-resource/mcp",
            "/.well-known/oauth-protected-resource" + path,
        }

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return
        if scope.get("client", ("", 0))[0] not in {"127.0.0.1", "::1"}:
            await Response(status_code=403)(scope, receive, send)
        elif scope.get("path") not in self.paths:
            await Response(status_code=404)(scope, receive, send)
        else:
            if scope["path"] == "/.well-known/oauth-protected-resource":
                path = "/.well-known/oauth-protected-resource/mcp"
                scope = {**scope, "path": path, "raw_path": path.encode()}
            await self.app(scope, receive, send)
