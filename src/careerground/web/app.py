"""Public web/BFF skeleton. No user-resource endpoint until provider auth exists."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from careerground.config import Settings
from careerground.storage.database import make_engine

app = FastAPI(title="CareerGround", version="0.1.0")


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
