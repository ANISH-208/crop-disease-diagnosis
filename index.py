"""Vercel FastAPI entry point for the Crop Doctor API service."""

from backend.main import app as fastapi_app


class VercelServicePrefix:
    """Accept both /health and /api/health after Vercel service routing."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] in {"http", "websocket"}:
            path = scope.get("path", "")
            if path == "/api" or path.startswith("/api/"):
                scope = dict(scope)
                scope["path"] = path[4:] or "/"
                scope["raw_path"] = scope["path"].encode("utf-8")
        await self.app(scope, receive, send)


app = VercelServicePrefix(fastapi_app)
