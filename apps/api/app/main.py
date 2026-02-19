import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import Base, engine
from app.routers import alerts, auth, exports, farms, fields, layers, organizations

configure_logging()
logger = logging.getLogger("app.validation")
settings = get_settings()
allowed_origins = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]

app = FastAPI(title="Field Monitoring Hybrid API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins or ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(organizations.router, prefix="/api/v1")
app.include_router(farms.router, prefix="/api/v1")
app.include_router(fields.router, prefix="/api/v1")
app.include_router(layers.router, prefix="/api/v1")
app.include_router(exports.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")


@app.on_event("startup")
def startup_event() -> None:
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
    Base.metadata.create_all(bind=engine)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    body = await request.body()
    body_preview = body.decode("utf-8", errors="ignore")
    if len(body_preview) > 2000:
        body_preview = f"{body_preview[:2000]}...[truncated]"
    logger.warning(
        "Request validation failed path=%s method=%s errors=%s body_preview=%s",
        request.url.path,
        request.method,
        exc.errors(),
        body_preview,
    )
    return JSONResponse(status_code=422, content={"detail": exc.errors()})


Instrumentator().instrument(app).expose(app, include_in_schema=False)


@app.get("/healthz", tags=["health"])
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}
