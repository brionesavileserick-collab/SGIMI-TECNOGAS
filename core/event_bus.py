"""
Event Bus - Central communication system for event-driven architecture.
Provides publish/subscribe pattern for decoupled module communication.
"""

from typing import Callable, Dict, List, Any
from collections import defaultdict, deque
import logging

logger = logging.getLogger(__name__)


class EventBus:
    """
    Central event bus for inter-module communication.
    Implements a simple publish/subscribe pattern.
    """

    def __init__(self, max_history_size: int = 1000):
        self._handlers: Dict[str, List[Callable]] = defaultdict(list)
        self._event_history: deque = deque(maxlen=max_history_size)
        self._max_history_size = max_history_size

    def subscribe(self, event: str, handler: Callable) -> None:
        """
        Subscribe a handler to an event.

        Args:
            event: Event name to subscribe to
            handler: Function to call when event is emitted
        """
        if handler not in self._handlers[event]:
            self._handlers[event].append(handler)
            logger.debug(f"Subscribed handler {handler.__name__} to event {event}")

    def unsubscribe(self, event: str, handler: Callable) -> None:
        """
        Unsubscribe a handler from an event.

        Args:
            event: Event name to unsubscribe from
            handler: Handler to remove
        """
        if handler in self._handlers[event]:
            self._handlers[event].remove(handler)
            logger.debug(f"Unsubscribed handler {handler.__name__} from event {event}")

    def emit(self, event: str, data: Any = None) -> None:
        """
        Emit an event to all subscribed handlers.

        Args:
            event: Event name to emit
            data: Data to pass to handlers
        """
        event_record = {
            "event": event,
            "data": data
        }
        self._event_history.append(event_record)
        logger.info(f"Event emitted: {event}")

        handlers = self._handlers.get(event, [])
        for handler in handlers:
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Error in handler {handler.__name__} for event {event}: {e}")

    def get_history(self, event: str = None) -> List[Dict[str, Any]]:
        """
        Get event history, optionally filtered by event name.

        Args:
            event: Optional event name to filter by

        Returns:
            List of event records
        """
        if event:
            return [e for e in self._event_history if e["event"] == event]
        return self._event_history.copy()

    def clear_history(self) -> None:
        """Clear event history."""
        self._event_history.clear()

    def list_subscriptions(self) -> Dict[str, List[str]]:
        """
        List all current subscriptions.

        Returns:
            Dictionary of events and their handler names
        """
        return {
            event: [h.__name__ for h in handlers]
            for event, handlers in self._handlers.items()
            if handlers
        }


# Global event bus instance
event_bus = EventBus()
