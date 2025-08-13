"""Base Agent Framework with State Management"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Callable
from enum import Enum
from datetime import datetime
import asyncio
import uuid
import json
from dataclasses import dataclass, field
from pydantic import BaseModel, Field

from .logging_config import get_logger
from .exceptions import AgentException


class AgentState(str, Enum):
    """Agent lifecycle states"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    READY = "ready"
    PROCESSING = "processing"
    ERROR = "error"
    SHUTDOWN = "shutdown"


class MessageType(str, Enum):
    """Types of messages agents can handle"""
    CALL_INTAKE = "call_intake"
    TRANSCRIPTION = "transcription"
    SUMMARY = "summary"
    QUALITY_SCORE = "quality_score"
    ROUTING = "routing"
    ERROR = "error"
    STATUS = "status"
    CONTROL = "control"


class Message(BaseModel):
    """Standard message format for inter-agent communication"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: MessageType
    sender: str
    recipient: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None
    reply_to: Optional[str] = None
    
    class Config:
        use_enum_values = True


@dataclass
class AgentConfig:
    """Configuration for agent initialization"""
    name: str
    type: str
    max_retries: int = 3
    timeout_seconds: int = 300
    enable_metrics: bool = True
    enable_logging: bool = True
    custom_config: Dict[str, Any] = field(default_factory=dict)


class AgentMetrics:
    """Track agent performance metrics"""
    
    def __init__(self):
        self.messages_processed = 0
        self.messages_failed = 0
        self.total_processing_time = 0.0
        self.average_processing_time = 0.0
        self.last_error = None
        self.last_error_time = None
        self.start_time = datetime.utcnow()
        
    def record_success(self, processing_time: float):
        self.messages_processed += 1
        self.total_processing_time += processing_time
        self.average_processing_time = (
            self.total_processing_time / self.messages_processed
        )
    
    def record_failure(self, error: str):
        self.messages_failed += 1
        self.last_error = error
        self.last_error_time = datetime.utcnow()
    
    def get_stats(self) -> Dict[str, Any]:
        uptime = (datetime.utcnow() - self.start_time).total_seconds()
        return {
            "messages_processed": self.messages_processed,
            "messages_failed": self.messages_failed,
            "success_rate": (
                self.messages_processed / 
                (self.messages_processed + self.messages_failed)
                if (self.messages_processed + self.messages_failed) > 0 else 0
            ),
            "average_processing_time": self.average_processing_time,
            "uptime_seconds": uptime,
            "last_error": self.last_error,
            "last_error_time": self.last_error_time.isoformat() if self.last_error_time else None
        }


class BaseAgent(ABC):
    """Base class for all agents in the system"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.id = str(uuid.uuid4())
        self.name = config.name
        self.type = config.type
        self.state = AgentState.IDLE
        self.logger = get_logger(f"{self.__class__.__name__}.{self.name}")
        self.metrics = AgentMetrics()
        
        # Message handling
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self.message_handlers: Dict[MessageType, Callable] = {}
        self.subscriptions: List[str] = []
        
        # State management
        self.state_data: Dict[str, Any] = {}
        self.state_history: List[tuple] = []
        
        # Lifecycle
        self._running = False
        self._tasks: List[asyncio.Task] = []
        
    async def initialize(self) -> None:
        """Initialize the agent"""
        try:
            self.set_state(AgentState.INITIALIZING)
            self.logger.info(f"Initializing agent {self.name}")
            
            # Register message handlers
            self._register_handlers()
            
            # Perform agent-specific initialization
            await self._initialize()
            
            self.set_state(AgentState.READY)
            self.logger.info(f"Agent {self.name} initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize agent {self.name}: {e}")
            self.set_state(AgentState.ERROR)
            raise AgentException(f"Initialization failed: {e}")
    
    @abstractmethod
    async def _initialize(self) -> None:
        """Agent-specific initialization logic"""
        pass
    
    def _register_handlers(self) -> None:
        """Register message handlers"""
        self.message_handlers[MessageType.STATUS] = self._handle_status_request
        self.message_handlers[MessageType.CONTROL] = self._handle_control_message
    
    async def start(self) -> None:
        """Start the agent"""
        if self.state != AgentState.READY:
            raise AgentException(f"Agent must be in READY state to start (current: {self.state})")
        
        self._running = True
        self.logger.info(f"Starting agent {self.name}")
        
        # Start message processing loop
        task = asyncio.create_task(self._process_messages())
        self._tasks.append(task)
        
        # Start agent-specific tasks
        await self._start()
    
    @abstractmethod
    async def _start(self) -> None:
        """Agent-specific start logic"""
        pass
    
    async def stop(self) -> None:
        """Stop the agent"""
        self.logger.info(f"Stopping agent {self.name}")
        self._running = False
        
        # Stop agent-specific tasks
        await self._stop()
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        self.set_state(AgentState.SHUTDOWN)
        self.logger.info(f"Agent {self.name} stopped")
    
    @abstractmethod
    async def _stop(self) -> None:
        """Agent-specific stop logic"""
        pass
    
    async def _process_messages(self) -> None:
        """Main message processing loop"""
        while self._running:
            try:
                # Get message with timeout
                message = await asyncio.wait_for(
                    self.message_queue.get(),
                    timeout=1.0
                )
                
                # Process message
                start_time = datetime.utcnow()
                await self._handle_message(message)
                processing_time = (datetime.utcnow() - start_time).total_seconds()
                
                self.metrics.record_success(processing_time)
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                self.logger.error(f"Error processing message: {e}")
                self.metrics.record_failure(str(e))
    
    async def _handle_message(self, message: Message) -> None:
        """Handle incoming message"""
        self.logger.debug(f"Handling message: {message.type} from {message.sender}")
        
        # Check if we have a handler for this message type
        handler = self.message_handlers.get(message.type)
        if handler:
            await handler(message)
        else:
            # Call agent-specific message handler
            await self.handle_message(message)
    
    @abstractmethod
    async def handle_message(self, message: Message) -> None:
        """Agent-specific message handling"""
        pass
    
    async def send_message(self, message: Message) -> None:
        """Send a message to another agent or component"""
        self.logger.debug(f"Sending message: {message.type} to {message.recipient}")
        # This will be implemented by the communication module
        # For now, we'll just log it
        pass
    
    async def receive_message(self, message: Message) -> None:
        """Receive a message"""
        await self.message_queue.put(message)
    
    def set_state(self, state: AgentState) -> None:
        """Update agent state"""
        old_state = self.state
        self.state = state
        self.state_history.append((old_state, state, datetime.utcnow()))
        self.logger.info(f"State transition: {old_state} -> {state}")
    
    def get_state(self) -> AgentState:
        """Get current agent state"""
        return self.state
    
    def set_state_data(self, key: str, value: Any) -> None:
        """Store state data"""
        self.state_data[key] = value
    
    def get_state_data(self, key: str, default: Any = None) -> Any:
        """Retrieve state data"""
        return self.state_data.get(key, default)
    
    async def _handle_status_request(self, message: Message) -> None:
        """Handle status request"""
        status = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "state": self.state.value,
            "metrics": self.metrics.get_stats(),
            "state_data": self.state_data
        }
        
        reply = Message(
            type=MessageType.STATUS,
            sender=self.name,
            recipient=message.sender,
            payload=status,
            reply_to=message.id
        )
        
        await self.send_message(reply)
    
    async def _handle_control_message(self, message: Message) -> None:
        """Handle control messages"""
        command = message.payload.get("command")
        
        if command == "restart":
            await self.restart()
        elif command == "reset_metrics":
            self.metrics = AgentMetrics()
        elif command == "clear_state":
            self.state_data.clear()
    
    async def restart(self) -> None:
        """Restart the agent"""
        self.logger.info(f"Restarting agent {self.name}")
        await self.stop()
        await self.initialize()
        await self.start()
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name='{self.name}' state={self.state}>"