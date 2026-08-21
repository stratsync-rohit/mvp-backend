"""
Custom application exceptions and their FastAPI exception handlers.

Centralizing this ensures we never leak internal details (DB errors, stack
traces, webhook URLs) to API consumers, and that error shapes are
consistent across the whole API: {"detail": "..."}.
"""
from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.utils.logger import get_logger

logger = get_logger(__name__)


class AppError(Exception):
    """Base class for application-level errors with an HTTP status code."""

    def __init__(self, detail: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


class RiskNotFoundError(AppError):
    def __init__(self, risk_id: str | None = None):
        super().__init__("Risk not found", status.HTTP_404_NOT_FOUND)


class RiskAlreadyExistsError(AppError):
    def __init__(self):
        super().__init__("Risk already exists", status.HTTP_409_CONFLICT)


class TeamsDestinationNotFoundError(AppError):
    def __init__(self):
        super().__init__("Teams destination not configured", status.HTTP_404_NOT_FOUND)


class TeamsDestinationDisabledError(AppError):
    def __init__(self):
        super().__init__("Teams destination is disabled", status.HTTP_409_CONFLICT)


class TeamsInstallationNotConfiguredError(AppError):
    def __init__(self):
        super().__init__(
            "Microsoft Teams integration is not connected for this account.",
            status.HTTP_409_CONFLICT,
        )


class TeamsRouteNotConfiguredError(AppError):
    def __init__(self, route_key: str):
        super().__init__(
            f"No active Microsoft Teams destination is configured for route '{route_key}'.",
            status.HTTP_409_CONFLICT,
        )


class TeamsRouteRequiredError(AppError):
    def __init__(self):
        super().__init__(
            "Multiple Microsoft Teams channels are connected. destinationId is required.",
            status.HTTP_409_CONFLICT,
        )


class TeamsRouteConflictError(AppError):
    def __init__(self):
        super().__init__(
            "An active Microsoft Teams destination already uses this route for the account.",
            status.HTTP_409_CONFLICT,
        )


class TeamsInstallationNotFoundError(AppError):
    def __init__(self):
        super().__init__("Microsoft Teams installation not found.", status.HTTP_404_NOT_FOUND)


class TeamsInstallationUnavailableError(AppError):
    def __init__(self):
        super().__init__(
            "Microsoft Teams destination is no longer connected.",
            status.HTTP_409_CONFLICT,
        )


class TeamsChannelDestinationNotFoundError(AppError):
    def __init__(self):
        super().__init__(
            "Microsoft Teams destination was not found for this account.",
            status.HTTP_404_NOT_FOUND,
        )


class TeamsChannelDestinationReconnectConflictError(AppError):
    def __init__(self):
        super().__init__(
            "Only a destination manually disconnected in StratSync can be reconnected. Reinstall the StratSync app in Microsoft Teams if it was removed.",
            status.HTTP_409_CONFLICT,
        )


class MicrosoftTenantNotMappedError(AppError):
    def __init__(self):
        super().__init__(
            "Microsoft tenant is not mapped to a StratSync account.",
            status.HTTP_409_CONFLICT,
        )


class MicrosoftTenantMappingDisabledError(AppError):
    def __init__(self):
        super().__init__(
            "Microsoft tenant mapping is disabled.",
            status.HTTP_409_CONFLICT,
        )


class TenantMappingNotFoundError(AppError):
    def __init__(self):
        super().__init__("Microsoft tenant mapping not found", status.HTTP_404_NOT_FOUND)


class N8nDeliveryError(AppError):
    def __init__(self, detail: str = "Unable to queue Microsoft Teams notification"):
        super().__init__(detail, status.HTTP_502_BAD_GATEWAY)


class NotificationLogNotFoundError(AppError):
    def __init__(self):
        super().__init__("Notification log not found", status.HTTP_404_NOT_FOUND)


class UnauthorizedError(AppError):
    def __init__(self, detail: str = "Invalid or missing internal API key"):
        super().__init__(detail, status.HTTP_401_UNAUTHORIZED)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = []
        for error in exc.errors():
            clean_error = {k: v for k, v in error.items() if k != "ctx"}
            errors.append(clean_error)

        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": jsonable_encoder(errors)},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        # Never leak internal details (DB errors, stack traces, credentials).
        logger.error(
            "Unhandled exception",
            extra={"path": str(request.url), "error_type": type(exc).__name__},
            exc_info=True,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )
