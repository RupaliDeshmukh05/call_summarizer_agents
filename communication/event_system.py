"""Event System for Call Center Events"""

import asyncio
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime
from enum import Enum
from dataclasses import dataclass
import json

from core import get_logger
from core.exceptions import CommunicationException


class EventType(str, Enum):
    """Types of system events"""
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    TRANSCRIPTION_COMPLETED = "transcription_completed"
    SUMMARY_GENERATED = "summary_generated"
    QUALITY_SCORED = "quality_scored"
    CALL_ROUTED = "call_routed"
    AGENT_ASSIGNED = "agent_assigned"
    ESCALATION_TRIGGERED = "escalation_triggered"
    SYSTEM_ALERT = "system_alert"
    PERFORMANCE_METRIC = "performance_metric"


@dataclass
class Event:
    """System event"""
    id: str
    type: EventType
    source: str
    timestamp: datetime
    data: Dict[str, Any]
    correlation_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "data": self.data,
            "correlation_id": self.correlation_id
        }


class EventListener:
    """Event listener configuration"""
    
    def __init__(self, event_types: List[EventType], handler: Callable, filter_func: Optional[Callable] = None):
        self.event_types = event_types
        self.handler = handler
        self.filter_func = filter_func
        self.created_at = datetime.utcnow()
        self.event_count = 0


class EventSystem:
    """Event system for managing system events"""
    
    def __init__(self, max_history: int = 1000):
        self.listeners: Dict[EventType, List[EventListener]] = {}
        self.event_history: List[Event] = []
        self.max_history = max_history
        self.logger = get_logger(__name__)
        self.is_running = False
        
        # Event processing queue
        self.event_queue: asyncio.Queue = asyncio.Queue()
        self.processor_task: Optional[asyncio.Task] = None
        
        # Metrics
        self.events_published = 0
        self.events_processed = 0
        self.listener_count = 0
    
    async def start(self) -> None:
        """Start the event system"""
        if self.is_running:
            return
        
        self.is_running = True
        self.processor_task = asyncio.create_task(self._process_events())
        self.logger.info("Event system started")
    
    async def stop(self) -> None:
        """Stop the event system"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.processor_task:
            self.processor_task.cancel()
            try:
                await self.processor_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Event system stopped")
    
    async def publish(self, event: Event) -> None:
        """Publish an event"""
        try:
            # Add to queue for processing
            await self.event_queue.put(event)
            self.events_published += 1
            
            self.logger.debug(f"Published event {event.id} of type {event.type.value}")
            
        except Exception as e:
            self.logger.error(f"Failed to publish event: {e}")
            raise CommunicationException(f"Event publish failed: {e}")
    
    def subscribe(
        self,
        event_types: List[EventType],
        handler: Callable,
        filter_func: Optional[Callable] = None
    ) -> str:
        """Subscribe to events"""
        try:
            listener = EventListener(event_types, handler, filter_func)
            listener_id = str(id(listener))
            
            # Add listener to each event type
            for event_type in event_types:
                if event_type not in self.listeners:
                    self.listeners[event_type] = []
                self.listeners[event_type].append(listener)
            
            self.listener_count += 1
            self.logger.info(f"Subscribed listener {listener_id} to events: {[et.value for et in event_types]}")
            
            return listener_id
            
        except Exception as e:
            self.logger.error(f"Failed to subscribe to events: {e}")
            raise CommunicationException(f"Event subscription failed: {e}")
    
    def unsubscribe(self, listener_id: str) -> None:
        """Unsubscribe from events"""
        try:
            # Remove listener from all event types
            for event_type in list(self.listeners.keys()):
                self.listeners[event_type] = [
                    listener for listener in self.listeners[event_type]
                    if str(id(listener)) != listener_id
                ]
                
                # Clean up empty event types
                if not self.listeners[event_type]:
                    del self.listeners[event_type]
            
            self.listener_count -= 1
            self.logger.info(f"Unsubscribed listener {listener_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe: {e}")
    
    async def _process_events(self) -> None:
        """Process events from the queue"""
        while self.is_running:
            try:
                # Get event with timeout
                event = await asyncio.wait_for(
                    self.event_queue.get(),
                    timeout=1.0
                )
                
                # Store in history
                self._add_to_history(event)
                
                # Notify listeners
                await self._notify_listeners(event)
                
                self.events_processed += 1
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")
    
    def _add_to_history(self, event: Event) -> None:
        """Add event to history"""
        self.event_history.append(event)
        
        # Trim history if too large
        if len(self.event_history) > self.max_history:
            self.event_history = self.event_history[-self.max_history:]
    
    async def _notify_listeners(self, event: Event) -> None:
        """Notify event listeners"""
        if event.type in self.listeners:
            for listener in self.listeners[event.type]:
                try:
                    # Apply filter if present
                    if listener.filter_func and not listener.filter_func(event):
                        continue
                    
                    # Call handler
                    await listener.handler(event)
                    listener.event_count += 1
                    
                except Exception as e:
                    self.logger.error(f"Error in event listener: {e}")
    
    def get_event_history(
        self,
        event_type: Optional[EventType] = None,
        source: Optional[str] = None,
        limit: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Get filtered event history"""
        events = self.event_history
        
        # Filter by event type
        if event_type:
            events = [e for e in events if e.type == event_type]
        
        # Filter by source
        if source:
            events = [e for e in events if e.source == source]
        
        # Apply limit
        if limit:
            events = events[-limit:]
        
        return [e.to_dict() for e in events]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get event system metrics"""
        return {
            "events_published": self.events_published,
            "events_processed": self.events_processed,
            "listener_count": self.listener_count,
            "event_types": len(self.listeners),
            "history_size": len(self.event_history),
            "is_running": self.is_running
        }
    
    def get_listener_stats(self) -> Dict[str, Any]:
        """Get listener statistics"""
        stats = {}
        
        for event_type, listeners in self.listeners.items():
            stats[event_type.value] = {
                "listener_count": len(listeners),
                "total_events_handled": sum(l.event_count for l in listeners)
            }
        
        return stats


# Event factory functions
def create_call_started_event(call_id: str, source: str, metadata: Dict[str, Any]) -> Event:
    """Create call started event"""
    import uuid
    return Event(
        id=str(uuid.uuid4()),
        type=EventType.CALL_STARTED,
        source=source,
        timestamp=datetime.utcnow(),
        data={
            "call_id": call_id,
            "metadata": metadata
        },
        correlation_id=call_id
    )


def create_call_ended_event(call_id: str, source: str, duration: float, outcome: str) -> Event:
    """Create call ended event"""
    import uuid
    return Event(
        id=str(uuid.uuid4()),
        type=EventType.CALL_ENDED,
        source=source,
        timestamp=datetime.utcnow(),
        data={
            "call_id": call_id,
            "duration": duration,
            "outcome": outcome
        },
        correlation_id=call_id
    )


def create_summary_generated_event(call_id: str, source: str, summary: Dict[str, Any]) -> Event:
    """Create summary generated event"""
    import uuid
    return Event(
        id=str(uuid.uuid4()),
        type=EventType.SUMMARY_GENERATED,
        source=source,
        timestamp=datetime.utcnow(),
        data={
            "call_id": call_id,
            "summary": summary
        },
        correlation_id=call_id
    )


def create_quality_scored_event(call_id: str, source: str, score: int, assessment: Dict[str, Any]) -> Event:
    """Create quality scored event"""
    import uuid
    return Event(
        id=str(uuid.uuid4()),
        type=EventType.QUALITY_SCORED,
        source=source,
        timestamp=datetime.utcnow(),
        data={
            "call_id": call_id,
            "score": score,
            "assessment": assessment
        },
        correlation_id=call_id
    )


def create_system_alert_event(source: str, alert_type: str, message: str, severity: str = "info") -> Event:
    """Create system alert event"""
    import uuid
    return Event(
        id=str(uuid.uuid4()),
        type=EventType.SYSTEM_ALERT,
        source=source,
        timestamp=datetime.utcnow(),
        data={
            "alert_type": alert_type,
            "message": message,
            "severity": severity
        }
    )