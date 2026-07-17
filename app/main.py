"""FastAPI application entrypoint."""

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.health import router as health_router
from app.api.webhooks import router as webhooks_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.session import dispose_database, initialize_database

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Initialize and release application resources."""
    settings = get_settings()
    configure_logging(settings.log_level)
    await initialize_database()
    logger.info("application_started")
    yield
    await dispose_database()
    logger.info("application_stopped")


def create_app() -> FastAPI:
    """Build the FastAPI application with its initial routes."""
    settings = get_settings()
    app = FastAPI(title=settings.app_name, debug=settings.debug, lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(webhooks_router)
    return app


app = create_app()
