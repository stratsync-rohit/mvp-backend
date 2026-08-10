"""
n8n integration service.

This is the ONLY module that talks to n8n over HTTP. It exposes a single
reusable `trigger_webhook` coroutine used for both the notification webhook
and (in the future) the action webhook.
"""
from typing import Any

import httpx

from app.config import get_settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class N8nDeliveryException(Exception):
    """Raised when n8n cannot be reached or returns a non-2xx response."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class N8nService:
    def __init__(self) -> None:
        self._settings = get_settings()

    async def trigger_webhook(self, url: str, payload: dict[str, Any], event_id: str) -> dict[str, Any]:
        """POST payload to an n8n webhook URL.

        Returns the parsed JSON response body (or an empty dict if n8n
        returns a non-JSON / empty body on success).

        Raises N8nDeliveryException on network errors or non-2xx responses -
        callers are responsible for translating this into a safe, generic
        API error (never leak n8n internals to the frontend).
        """
        headers = {"X-Correlation-ID": event_id, "Content-Type": "application/json"}
        timeout = self._settings.n8n_timeout_seconds

        logger.info("Calling n8n webhook", extra={"event_id": event_id})

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.post(url, json=payload, headers=headers)
        except httpx.RequestError as exc:
            logger.error(
                "n8n webhook network error",
                extra={"event_id": event_id, "error_type": type(exc).__name__},
            )
            raise N8nDeliveryException("Network error while calling n8n") from exc

        if response.status_code >= 400:
            logger.error(
                "n8n webhook returned error status",
                extra={"event_id": event_id, "status_code": response.status_code},
            )
            raise N8nDeliveryException(f"n8n returned status {response.status_code}")

        try:
            return response.json()
        except ValueError:
            # n8n may respond with an empty body / plain text on success.
            return {}
