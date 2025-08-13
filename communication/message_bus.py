"""Message Bus System for Inter-Agent Communication"""

import asyncio
import json
from typing import Dict, List, Callable, Any, Optional, Set
from datetime import datetime
from enum import Enum
from abc import ABC, abstractmethod
import aio_pika
from aio_pika.abc import AbstractConnection, AbstractChannel, AbstractQueue
import redis.asyncio as redis

from core import get_logger
from core.base_agent import Message, MessageType
from core.exceptions import CommunicationException


class MessageBrokerType(str, Enum):
    """Types of message brokers"""
    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    MEMORY = "memory"


class MessageHandler:
    """Handler for processing messages"""
    
    def __init__(self, handler_func: Callable, message_types: List[MessageType]):
        self.handler_func = handler_func
        self.message_types = message_types
        self.registered_at = datetime.utcnow()
        self.message_count = 0


class MessageBroker(ABC):
    """Abstract base class for message brokers"""
    
    @abstractmethod
    async def connect(self) -> None:
        """Connect to the message broker"""
        pass
    
    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the message broker"""
        pass
    
    @abstractmethod
    async def publish(self, topic: str, message: Message) -> None:
        """Publish a message to a topic"""
        pass
    
    @abstractmethod
    async def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to a topic"""
        pass
    
    @abstractmethod
    async def unsubscribe(self, topic: str, handler_id: str) -> None:
        """Unsubscribe from a topic"""
        pass


class RabbitMQBroker(MessageBroker):
    """RabbitMQ message broker implementation"""
    
    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self.connection: Optional[AbstractConnection] = None
        self.channel: Optional[AbstractChannel] = None
        self.queues: Dict[str, AbstractQueue] = {}
        self.logger = get_logger(__name__)
    
    async def connect(self) -> None:
        """Connect to RabbitMQ"""
        try:
            self.connection = await aio_pika.connect_robust(self.connection_url)
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=10)
            self.logger.info("Connected to RabbitMQ")
            
        except Exception as e:
            raise CommunicationException(f"Failed to connect to RabbitMQ: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ"""
        if self.connection:
            await self.connection.close()
            self.logger.info("Disconnected from RabbitMQ")
    
    async def publish(self, topic: str, message: Message) -> None:
        """Publish message to RabbitMQ exchange"""
        try:
            if not self.channel:
                raise CommunicationException("Not connected to RabbitMQ")
            
            # Create exchange if not exists
            exchange = await self.channel.declare_exchange(
                f"call_center_{topic}",
                aio_pika.ExchangeType.FANOUT,
                durable=True
            )
            
            # Serialize message
            message_body = json.dumps(message.dict()).encode()
            
            # Publish message
            await exchange.publish(
                aio_pika.Message(
                    message_body,
                    content_type="application/json",
                    message_id=message.id,
                    timestamp=datetime.utcnow()
                ),
                routing_key=""
            )
            
        except Exception as e:
            raise CommunicationException(f"Failed to publish message: {e}")
    
    async def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to RabbitMQ queue"""
        try:
            if not self.channel:
                raise CommunicationException("Not connected to RabbitMQ")
            
            # Create exchange
            exchange = await self.channel.declare_exchange(
                f"call_center_{topic}",
                aio_pika.ExchangeType.FANOUT,
                durable=True
            )
            
            # Create queue
            queue = await self.channel.declare_queue(
                f"queue_{topic}_{id(handler)}",
                durable=True,
                auto_delete=True
            )
            
            # Bind queue to exchange
            await queue.bind(exchange)
            
            # Set up consumer
            async def message_consumer(rabbit_message):
                async with rabbit_message.process():
                    try:
                        data = json.loads(rabbit_message.body.decode())
                        message = Message(**data)
                        await handler(message)
                    except Exception as e:
                        self.logger.error(f"Error processing message: {e}")
            
            await queue.consume(message_consumer)
            self.queues[f"{topic}_{id(handler)}"] = queue
            
        except Exception as e:
            raise CommunicationException(f"Failed to subscribe: {e}")
    
    async def unsubscribe(self, topic: str, handler_id: str) -> None:
        """Unsubscribe from topic"""
        queue_name = f"{topic}_{handler_id}"
        if queue_name in self.queues:
            await self.queues[queue_name].cancel()
            del self.queues[queue_name]


class RedisBroker(MessageBroker):
    """Redis message broker implementation"""
    
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.redis_client: Optional[redis.Redis] = None
        self.pubsub = None
        self.subscriptions: Dict[str, Set[Callable]] = {}
        self.logger = get_logger(__name__)
        self._listening = False
    
    async def connect(self) -> None:
        """Connect to Redis"""
        try:
            self.redis_client = redis.from_url(self.redis_url)
            await self.redis_client.ping()
            self.pubsub = self.redis_client.pubsub()
            self.logger.info("Connected to Redis")
            
        except Exception as e:
            raise CommunicationException(f"Failed to connect to Redis: {e}")
    
    async def disconnect(self) -> None:
        """Disconnect from Redis"""
        if self.pubsub:
            await self.pubsub.close()
        if self.redis_client:
            await self.redis_client.close()
        self._listening = False
        self.logger.info("Disconnected from Redis")
    
    async def publish(self, topic: str, message: Message) -> None:
        """Publish message to Redis channel"""
        try:
            if not self.redis_client:
                raise CommunicationException("Not connected to Redis")
            
            channel = f"call_center_{topic}"
            message_data = json.dumps(message.dict())
            await self.redis_client.publish(channel, message_data)
            
        except Exception as e:
            raise CommunicationException(f"Failed to publish message: {e}")
    
    async def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to Redis channel"""
        try:
            if not self.pubsub:
                raise CommunicationException("Not connected to Redis")
            
            channel = f"call_center_{topic}"
            
            # Add handler to subscriptions
            if channel not in self.subscriptions:
                self.subscriptions[channel] = set()
                await self.pubsub.subscribe(channel)
            
            self.subscriptions[channel].add(handler)
            
            # Start listening if not already started
            if not self._listening:
                asyncio.create_task(self._listen_for_messages())
                self._listening = True
                
        except Exception as e:
            raise CommunicationException(f"Failed to subscribe: {e}")
    
    async def _listen_for_messages(self) -> None:
        """Listen for Redis messages"""
        try:
            async for redis_message in self.pubsub.listen():
                if redis_message["type"] == "message":
                    channel = redis_message["channel"].decode()
                    data = json.loads(redis_message["data"].decode())
                    message = Message(**data)
                    
                    # Call all handlers for this channel
                    if channel in self.subscriptions:
                        for handler in self.subscriptions[channel]:
                            try:
                                await handler(message)
                            except Exception as e:
                                self.logger.error(f"Error in message handler: {e}")
                                
        except Exception as e:
            self.logger.error(f"Error listening for messages: {e}")
    
    async def unsubscribe(self, topic: str, handler_id: str) -> None:
        """Unsubscribe from topic"""
        channel = f"call_center_{topic}"
        # In production, implement proper handler tracking by ID
        if channel in self.subscriptions and self.subscriptions[channel]:
            self.subscriptions[channel].clear()
            await self.pubsub.unsubscribe(channel)


class MemoryBroker(MessageBroker):
    """In-memory message broker for testing"""
    
    def __init__(self):
        self.subscriptions: Dict[str, List[Callable]] = {}
        self.logger = get_logger(__name__)
    
    async def connect(self) -> None:
        """Connect (no-op for memory broker)"""
        self.logger.info("Memory broker connected")
    
    async def disconnect(self) -> None:
        """Disconnect (no-op for memory broker)"""
        self.logger.info("Memory broker disconnected")
    
    async def publish(self, topic: str, message: Message) -> None:
        """Publish message to memory subscribers"""
        if topic in self.subscriptions:
            for handler in self.subscriptions[topic]:
                try:
                    await handler(message)
                except Exception as e:
                    self.logger.error(f"Error in message handler: {e}")
    
    async def subscribe(self, topic: str, handler: Callable) -> None:
        """Subscribe to topic in memory"""
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        self.subscriptions[topic].append(handler)
    
    async def unsubscribe(self, topic: str, handler_id: str) -> None:
        """Unsubscribe from topic"""
        # Simple implementation - in production, track handlers by ID
        if topic in self.subscriptions:
            self.subscriptions[topic].clear()


class MessageBus:
    """Central message bus for inter-agent communication"""
    
    def __init__(self, broker_type: MessageBrokerType, connection_config: Dict[str, Any]):
        self.broker_type = broker_type
        self.connection_config = connection_config
        self.broker: Optional[MessageBroker] = None
        self.handlers: Dict[str, List[MessageHandler]] = {}
        self.message_history: List[Dict[str, Any]] = []
        self.logger = get_logger(__name__)
        self.is_connected = False
        
        # Metrics
        self.messages_sent = 0
        self.messages_received = 0
        self.errors = 0
    
    async def initialize(self) -> None:
        """Initialize the message bus"""
        try:
            # Create broker instance
            if self.broker_type == MessageBrokerType.RABBITMQ:
                self.broker = RabbitMQBroker(self.connection_config.get("url"))
            elif self.broker_type == MessageBrokerType.REDIS:
                self.broker = RedisBroker(self.connection_config.get("url"))
            else:
                self.broker = MemoryBroker()
            
            # Connect to broker
            await self.broker.connect()
            self.is_connected = True
            
            self.logger.info(f"Message bus initialized with {self.broker_type.value} broker")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize message bus: {e}")
            raise CommunicationException(f"Message bus initialization failed: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown the message bus"""
        if self.broker:
            await self.broker.disconnect()
        self.is_connected = False
        self.logger.info("Message bus shutdown")
    
    async def publish(self, topic: str, message: Message) -> None:
        """Publish a message to a topic"""
        try:
            if not self.is_connected:
                raise CommunicationException("Message bus not connected")
            
            await self.broker.publish(topic, message)
            self.messages_sent += 1
            
            # Record in history
            self.message_history.append({
                "topic": topic,
                "message_id": message.id,
                "message_type": message.type.value,
                "sender": message.sender,
                "recipient": message.recipient,
                "timestamp": datetime.utcnow().isoformat(),
                "action": "published"
            })
            
            self.logger.debug(f"Published message {message.id} to topic {topic}")
            
        except Exception as e:
            self.errors += 1
            self.logger.error(f"Failed to publish message: {e}")
            raise CommunicationException(f"Publish failed: {e}")
    
    async def subscribe(
        self,
        topic: str,
        handler_func: Callable,
        message_types: Optional[List[MessageType]] = None
    ) -> str:
        """Subscribe to a topic with a message handler"""
        try:
            if not self.is_connected:
                raise CommunicationException("Message bus not connected")
            
            # Create handler wrapper
            async def wrapped_handler(message: Message) -> None:
                try:
                    # Filter by message type if specified
                    if message_types and message.type not in message_types:
                        return
                    
                    await handler_func(message)
                    self.messages_received += 1
                    
                    # Update handler metrics
                    handler_id = id(handler_func)
                    if topic in self.handlers:
                        for handler in self.handlers[topic]:
                            if id(handler.handler_func) == handler_id:
                                handler.message_count += 1
                                break
                    
                except Exception as e:
                    self.errors += 1
                    self.logger.error(f"Error in message handler: {e}")
            
            # Subscribe to broker
            await self.broker.subscribe(topic, wrapped_handler)
            
            # Track handler
            if topic not in self.handlers:
                self.handlers[topic] = []
            
            handler = MessageHandler(handler_func, message_types or [])
            self.handlers[topic].append(handler)
            
            handler_id = str(id(handler_func))
            self.logger.info(f"Subscribed handler {handler_id} to topic {topic}")
            
            return handler_id
            
        except Exception as e:
            self.errors += 1
            self.logger.error(f"Failed to subscribe: {e}")
            raise CommunicationException(f"Subscribe failed: {e}")
    
    async def unsubscribe(self, topic: str, handler_id: str) -> None:
        """Unsubscribe a handler from a topic"""
        try:
            await self.broker.unsubscribe(topic, handler_id)
            
            # Remove from handlers
            if topic in self.handlers:
                self.handlers[topic] = [
                    h for h in self.handlers[topic]
                    if str(id(h.handler_func)) != handler_id
                ]
            
            self.logger.info(f"Unsubscribed handler {handler_id} from topic {topic}")
            
        except Exception as e:
            self.logger.error(f"Failed to unsubscribe: {e}")
            raise CommunicationException(f"Unsubscribe failed: {e}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get message bus metrics"""
        return {
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "errors": self.errors,
            "topics": len(self.handlers),
            "total_handlers": sum(len(handlers) for handlers in self.handlers.values()),
            "is_connected": self.is_connected,
            "broker_type": self.broker_type.value
        }
    
    def get_topic_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about topics and handlers"""
        topic_info = {}
        
        for topic, handlers in self.handlers.items():
            topic_info[topic] = {
                "handler_count": len(handlers),
                "total_messages": sum(h.message_count for h in handlers),
                "handlers": [
                    {
                        "id": str(id(h.handler_func)),
                        "message_types": [mt.value for mt in h.message_types],
                        "message_count": h.message_count,
                        "registered_at": h.registered_at.isoformat()
                    }
                    for h in handlers
                ]
            }
        
        return topic_info