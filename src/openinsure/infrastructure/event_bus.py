"""Event Grid / Service Bus adapter for domain-event publishing and processing.

Supports publishing events to Azure Event Grid topics and consuming
messages from Azure Service Bus queues, including dead-letter handling.
Authentication uses ``DefaultAzureCredential``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from uuid import UUID, uuid4

import structlog
from azure.core.credentials import AzureKeyCredential
from azure.eventgrid import EventGridPublisherClient
from azure.identity import DefaultAzureCredential
from azure.servicebus import ServiceBusClient

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from azure.servicebus.aio import ServiceBusClient as AsyncServiceBusClient

logger = structlog.get_logger()


class DomainEvent:
    """Lightweight wrapper for a domain event payload."""

    def __init__(
        self,
        event_type: str,
        subject: str,
        data: dict[str, Any],
        *,
        event_id: UUID | None = None,
        correlation_id: UUID | None = None,
    ) -> None:
        self.event_id = event_id or uuid4()
        self.event_type = event_type
        self.subject = subject
        self.data = data
        self.event_time = datetime.now(UTC)
        self.correlation_id = correlation_id

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.event_id),
            "eventType": self.event_type,
            "subject": self.subject,
            "data": self.data,
            "eventTime": self.event_time.isoformat(),
            "dataVersion": "1.0",
            "correlationId": str(self.correlation_id) if self.correlation_id else None,
        }


class EventBusAdapter:
    """Unified adapter for publishing events and consuming messages.

    Parameters
    ----------
    event_grid_endpoint:
        Event Grid topic endpoint URL.
    event_grid_key:
        Event Grid topic access key.  If *None*, ``DefaultAzureCredential``
        is used (requires Event Grid Data Sender role).
    service_bus_connection_string:
        Fully-qualified Service Bus namespace connection string.
    credential:
        Optional explicit Azure credential for Service Bus AAD auth.
    """

    def __init__(
        self,
        *,
        event_grid_endpoint: str | None = None,
        event_grid_key: str | None = None,
        service_bus_connection_string: str | None = None,
        service_bus_namespace: str | None = None,
        credential: DefaultAzureCredential | None = None,
    ) -> None:
        self._credential = credential or DefaultAzureCredential()

        # --- Event Grid publisher ---
        self._eg_client: EventGridPublisherClient | None = None
        if event_grid_endpoint:
            eg_cred: Any = AzureKeyCredential(event_grid_key) if event_grid_key else self._credential
            self._eg_client = EventGridPublisherClient(
                endpoint=event_grid_endpoint,
                credential=eg_cred,
            )

        # --- Service Bus consumer ---
        self._sb_client: ServiceBusClient | None = None
        self._async_sb_client: AsyncServiceBusClient | None = None
        if service_bus_connection_string:
            self._sb_client = ServiceBusClient.from_connection_string(service_bus_connection_string)
        elif service_bus_namespace:
            self._sb_client = ServiceBusClient(
                fully_qualified_namespace=service_bus_namespace,
                credential=self._credential,
            )

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish_event(self, event: DomainEvent) -> None:
        """Publish a single domain event to Event Grid."""
        if self._eg_client is None:
            raise RuntimeError("Event Grid client not configured")

        self._eg_client.send(event.to_dict())
        logger.info(
            "event_bus.published",
            event_id=str(event.event_id),
            event_type=event.event_type,
            subject=event.subject,
        )

    async def publish_events(self, events: list[DomainEvent]) -> None:
        """Publish a batch of domain events."""
        if self._eg_client is None:
            raise RuntimeError("Event Grid client not configured")

        batch = [e.to_dict() for e in events]
        self._eg_client.send(batch)
        logger.info("event_bus.batch_published", count=len(events))

    # ------------------------------------------------------------------
    # Consuming (Service Bus)
    # ------------------------------------------------------------------

    async def subscribe(
        self,
        queue_name: str,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
        *,
        max_messages: int = 10,
        max_wait_time: int = 5,
    ) -> None:
        """Receive and process messages from a Service Bus queue.

        The *handler* coroutine is called for each message body (parsed
        as JSON).  Successfully processed messages are completed;
        failures are dead-lettered.
        """
        if self._sb_client is None:
            raise RuntimeError("Service Bus client not configured")

        receiver = self._sb_client.get_queue_receiver(
            queue_name=queue_name,
            max_wait_time=max_wait_time,
        )

        with receiver:
            messages = receiver.receive_messages(
                max_message_count=max_messages,
                max_wait_time=max_wait_time,
            )
            for msg in messages:
                body = json.loads(str(msg))
                try:
                    await handler(body)
                    receiver.complete_message(msg)
                    logger.debug("event_bus.message_completed", queue=queue_name)
                except Exception:
                    logger.exception(
                        "event_bus.message_failed",
                        queue=queue_name,
                    )
                    receiver.dead_letter_message(
                        msg,
                        reason="ProcessingError",
                        error_description="Handler raised an exception",
                    )

    async def process_events(
        self,
        queue_name: str,
        handler: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
        *,
        max_messages: int = 10,
    ) -> int:
        """One-shot: receive a batch of messages and process them.

        Returns the number of messages successfully processed.
        """
        if self._sb_client is None:
            raise RuntimeError("Service Bus client not configured")

        processed = 0
        receiver = self._sb_client.get_queue_receiver(
            queue_name=queue_name,
            max_wait_time=5,
        )
        with receiver:
            messages = receiver.receive_messages(
                max_message_count=max_messages,
                max_wait_time=5,
            )
            for msg in messages:
                body = json.loads(str(msg))
                try:
                    await handler(body)
                    receiver.complete_message(msg)
                    processed += 1
                except Exception:
                    logger.exception("event_bus.process_error", queue=queue_name)
                    receiver.dead_letter_message(
                        msg,
                        reason="ProcessingError",
                        error_description="Handler raised an exception",
                    )

        logger.info(
            "event_bus.process_events_complete",
            queue=queue_name,
            processed=processed,
            total=len(messages),
        )
        return processed

    # ------------------------------------------------------------------
    # Dead-letter queue
    # ------------------------------------------------------------------

    async def receive_dead_letters(
        self,
        queue_name: str,
        *,
        max_messages: int = 10,
    ) -> list[dict[str, Any]]:
        """Read messages from the dead-letter sub-queue for inspection."""
        if self._sb_client is None:
            raise RuntimeError("Service Bus client not configured")

        receiver = self._sb_client.get_queue_receiver(
            queue_name=queue_name,
            sub_queue="deadletter",
            max_wait_time=5,
        )
        results: list[dict[str, Any]] = []
        with receiver:
            messages = receiver.receive_messages(
                max_message_count=max_messages,
                max_wait_time=5,
            )
            for msg in messages:
                results.append(
                    {
                        "body": json.loads(str(msg)),
                        "dead_letter_reason": msg.dead_letter_reason,
                        "dead_letter_error_description": msg.dead_letter_error_description,
                        "enqueued_time": str(msg.enqueued_time_utc),
                    }
                )
                receiver.complete_message(msg)

        logger.info(
            "event_bus.dead_letters_received",
            queue=queue_name,
            count=len(results),
        )
        return results

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        """Close underlying clients."""
        if self._sb_client:
            self._sb_client.close()
        if self._eg_client:
            self._eg_client.close()
        logger.info("event_bus.closed")
