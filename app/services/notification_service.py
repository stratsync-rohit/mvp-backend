"""
Notification service - orchestrates the "Send to Teams" flow.

Flow:
  1. Load latest risk from MongoDB (via RiskService)
  2. Resolve accountId -> Teams destination
  3. Verify destination is enabled
  4. Build the clean notification payload
  5. Create a pending notification log
  6. POST to n8n
  7. Mark the log success/failed
  8. Return a safe response to the frontend

Idempotency: if an `Idempotency-Key` header was supplied and we've already
successfully processed it, we short-circuit and return the previous result
instead of re-triggering n8n.
"""
import uuid
from typing import Any, Optional

from app.exceptions.handlers import N8nDeliveryError
from app.models.risk import EventType, LogStatus
from app.repositories.idempotency_repository import IdempotencyRepository
from app.repositories.notification_log_repository import NotificationLogRepository
from app.services.n8n_service import N8nDeliveryException, N8nService
from app.services.risk_service import RiskService
from app.services.teams_channel_destination_service import TeamsChannelDestinationService
from app.utils.logger import get_logger

logger = get_logger(__name__)

IDEMPOTENCY_SCOPE_SEND_TO_TEAMS = "send_to_teams"


class NotificationService:
    def __init__(
        self,
        risk_service: RiskService,
        channel_destination_service: TeamsChannelDestinationService,
        notification_log_repository: NotificationLogRepository,
        idempotency_repository: IdempotencyRepository,
        n8n_service: N8nService,
    ):
        self._risk_service = risk_service
        self._channel_destination_service = channel_destination_service
        self._log_repo = notification_log_repository
        self._idempotency_repo = idempotency_repository
        self._n8n_service = n8n_service
        self._settings_webhook_url = None  # resolved lazily from config

    async def send_to_teams(
        self,
        account_id: str,
        risk_id: str,
        requested_by: Optional[str] = None,
        installation_id: Optional[str] = None,
        destination_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> dict[str, Any]:
        # Load within account scope before any idempotency or destination lookup.
        risk = await self._risk_service.get_risk(account_id, risk_id)
        idempotency_scope = f"{IDEMPOTENCY_SCOPE_SEND_TO_TEAMS}:{account_id}"

        # 0. Idempotency short-circuit
        if idempotency_key:
            existing = await self._idempotency_repo.get(
                idempotency_key, idempotency_scope
            )
            if existing:
                logger.info(
                    "Idempotency key matched, returning cached result",
                    extra={"idempotency_key": idempotency_key, "risk_id": risk_id},
                )
                return existing["result"]

        # Channel destinations are the only notification-routing authority.
        if destination_id:
            destination = await self._channel_destination_service.resolve_selected(
                account_id, destination_id
            )
        else:
            if installation_id:
                logger.warning(
                    "installationId routing is deprecated; resolving the sole active channel",
                    extra={"accountId": account_id},
                )
            destination = await self._channel_destination_service.resolve_default(
                account_id
            )
        resolved_destination_id = str(destination["_id"])

        # 4. Build clean notification payload
        notification = await self._risk_service.get_notification_payload(account_id, risk_id)

        # 5. Generate event/correlation id + pending log
        event_id = str(uuid.uuid4())
        await self._log_repo.create_pending(
            {
                "eventId": event_id,
                "riskId": risk_id,
                "eventType": EventType.INITIAL_NOTIFICATION.value,
                "actionKey": None,
                "accountId": account_id,
                "teamId": destination.get("teamId"),
                "channelId": destination.get("channelId"),
                "n8nResponse": {},
                "errorMessage": None,
            }
        )

        payload = {
            "eventId": event_id,
            "eventType": EventType.INITIAL_NOTIFICATION.value,
            "riskId": risk_id,
            "accountId": account_id,
            "destination": {
                "teamId": destination.get("teamId"),
                "channelId": destination.get("channelId"),
            },
            "teamsDestination": {
                "destinationId": resolved_destination_id,
                "tenantId": destination["tenantId"],
                "teamId": destination.get("teamId"),
                "channelId": destination.get("channelId"),
                "conversationId": destination["conversationId"],
                "serviceUrl": destination["serviceUrl"],
            },
            "notification": notification,
        }
        if requested_by:
            payload["requestedBy"] = requested_by

        # 6/7. Call n8n and update the log accordingly
        from app.config import get_settings  # local import keeps module import-time light

        webhook_url = get_settings().n8n_notification_webhook_url

        try:
            n8n_response = await self._n8n_service.trigger_webhook(webhook_url, payload, event_id)
        except N8nDeliveryException as exc:
            await self._log_repo.mark_failed(event_id, exc.message)
            raise N8nDeliveryError() from exc

        await self._channel_destination_service.record_delivery_result(
            account_id, resolved_destination_id, n8n_response,
        )
        if n8n_response.get("success") is False:
            await self._log_repo.mark_failed(event_id, "Microsoft Teams delivery failed")
            raise N8nDeliveryError("Unable to deliver Microsoft Teams notification")

        await self._log_repo.mark_success(event_id, n8n_response)

        result = {
            "success": True,
            "eventId": event_id,
            "riskId": risk_id,
            "message": "Risk notification queued for Microsoft Teams",
        }

        if idempotency_key:
            await self._idempotency_repo.save_result(
                idempotency_key, idempotency_scope, result
            )

        return result
