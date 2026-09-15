import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import router
from app.core.config import get_settings
from app.core.errors import AppError, app_error_handler
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger(__name__)
STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info(
        "application_started",
        extra={"provider": settings.llm_provider, "model": settings.provider_model},
    )
    yield
    logger.info("application_stopped")


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Grounded product and growth guidance from Lenny's Podcast transcripts.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-User-Id", "X-Request-Id"],
)
app.add_exception_handler(AppError, app_error_handler)


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, _: SQLAlchemyError) -> JSONResponse:
    logger.exception("database_request_failed", extra={"trace_id": request.state.trace_id})
    return JSONResponse(
        status_code=503,
        content={
            "error": {
                "code": "database_unavailable",
                "message": "Conversation storage is unavailable. No new state was saved.",
                "details": {},
            }
        },
    )


@app.exception_handler(Exception)
async def unexpected_error(request: Request, _: Exception) -> JSONResponse:
    logger.exception("unexpected_request_failure", extra={"trace_id": request.state.trace_id})
    return JSONResponse(
        status_code=500,
        content={
            "error": {
                "code": "internal_error",
                "message": "The request could not be completed.",
                "details": {},
            }
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "validation_error",
                "message": "The request was invalid.",
                "details": {"fields": jsonable_encoder(exc.errors())},
            }
        },
    )


@app.middleware("http")
async def request_context(request: Request, call_next):
    trace_id = request.headers.get("X-Request-Id", str(uuid4()))[:100]
    request.state.trace_id = trace_id
    started = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request_failed", extra={"trace_id": trace_id, "path": request.url.path})
        raise
    duration_ms = round((time.perf_counter() - started) * 1000, 1)
    response.headers["X-Request-Id"] = trace_id
    logger.info(
        "request_completed",
        extra={
            "trace_id": trace_id,
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    return response


app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")
