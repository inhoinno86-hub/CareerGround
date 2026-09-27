"""Public web/BFF skeleton. Auth0 login routes mount only when AUTH0_* is configured."""

from __future__ import annotations

from auth0_fastapi.auth import AuthClient
from auth0_fastapi.config import Auth0Config
from auth0_fastapi.server.routes import register_auth_routes
from fastapi import APIRouter, FastAPI, HTTPException, Request, Response
from sqlalchemy import text

from careerground.config import Auth0Settings, Settings
from careerground.storage.database import make_engine

app = FastAPI(title="CareerGround", version="0.1.0")


def _mount_auth0(settings: Auth0Settings) -> None:
    config = Auth0Config(
        domain=settings.domain,
        client_id=settings.client_id,
        client_secret=settings.client_secret,
        app_base_url=settings.app_base_url,
        secret=settings.secret,
        authorization_params={"scope": "openid profile email"},
    )
    auth_client = AuthClient(config)
    app.state.auth_client = auth_client
    router = APIRouter()
    # /auth/login, /auth/callback, /auth/logout, /auth/backchannel-logout
    register_auth_routes(router, config)

    @router.get("/auth/me")
    async def me(request: Request, response: Response) -> dict[str, str]:
        session = await auth_client.require_session(request, response)
        return {"sub": session["user"]["sub"]}

    app.include_router(router)


_auth0_settings = Auth0Settings.from_environment()
if _auth0_settings is not None:
    _mount_auth0(_auth0_settings)


@app.get("/", include_in_schema=False)
def home() -> dict[str, str]:
    """Small local landing target for Auth0's post-login redirect."""

    return {"service": "CareerGround", "session_check": "/auth/me"}


@app.get("/health/live", include_in_schema=False)
def live() -> dict[str, str]:
    return {"status": "live"}


@app.get("/health/ready", include_in_schema=False)
def ready() -> dict[str, str]:
    try:
        settings = Settings.from_environment()
        if settings.database_url is None:
            raise HTTPException(status_code=503, detail="database not configured")
        engine = make_engine(settings)
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        finally:
            engine.dispose()
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
