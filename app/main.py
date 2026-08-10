"""
FastAPI application entrypoint.

Wires together: lifespan-managed MongoDB connection, CORS, correlation-ID
middleware, exception handlers, and all routers.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import close_mongo_connection, connect_to_mongo
from app.exceptions.handlers import register_exception_handlers
from app.routers import health, notification_logs, risk_actions, risks, teams
from app.utils.logger import configure_logging, get_logger
from app.utils.middleware import CorrelationIdMiddleware

configure_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Risk Notification Backend")
    await connect_to_mongo()
    yield
    logger.info("Shutting down Risk Notification Backend")
    await close_mongo_connection()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description=(
            "Backend for the Microsoft Teams Risk Notification System. "
            "Stores risk data, serves the frontend, triggers n8n workflows, and "
            "processes action requests coming back from the Teams bot."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    app.add_middleware(CorrelationIdMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(risks.router)
    app.include_router(risk_actions.router)
    app.include_router(teams.router)
    app.include_router(notification_logs.router)

    return app


app = create_app()
