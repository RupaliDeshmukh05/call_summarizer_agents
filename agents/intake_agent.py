"""Call Intake Agent - Handles initial call reception and metadata extraction"""

import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, validator
import re

from core import BaseAgent, AgentConfig, AgentState, get_logger
from core.base_agent import Message, MessageType
from core.exceptions import AgentException, ValidationException


class CallMetadata(BaseModel):
    """Model for call metadata"""
    call_id: str
    customer_name: Optional[str] = None
    customer_phone: str
    account_number: Optional[str] = None
    call_reason: Optional[str] = None
    priority: str = "normal"  # low, normal, high, urgent
    language: str = "en"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @validator("customer_phone")
    def validate_phone(cls, v):
        # Basic phone validation
        phone_pattern = re.compile(r'^\+?1?\d{9,15}$')
        if not phone_pattern.match(v.replace("-", "").replace(" ", "")):
            raise ValueError("Invalid phone number format")
        return v
    
    @validator("priority")
    def validate_priority(cls, v):
        valid_priorities = ["low", "normal", "high", "urgent"]
        if v not in valid_priorities:
            raise ValueError(f"Priority must be one of {valid_priorities}")
        return v


class IntakeAgent(BaseAgent):
    """Agent responsible for initial call intake and validation"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.active_calls: Dict[str, CallMetadata] = {}
        self.greeting_template = config.custom_config.get(
            "greeting_template",
            "Thank you for calling {company_name}. My name is {agent_name}. How may I assist you today?"
        )
        self.company_name = config.custom_config.get("company_name", "AI Call Center")
        
    async def _initialize(self) -> None:
        """Initialize the intake agent"""
        self.logger.info("Initializing Intake Agent")
        
        # Load any predefined scripts or configurations
        self.intake_scripts = self._load_intake_scripts()
        
        # Initialize telephony connection if configured
        if self.config.custom_config.get("enable_telephony"):
            await self._initialize_telephony()
    
    async def _start(self) -> None:
        """Start the intake agent"""
        self.logger.info("Starting Intake Agent")
        
        # Start monitoring for incoming calls
        if self.config.custom_config.get("enable_telephony"):
            task = asyncio.create_task(self._monitor_incoming_calls())
            self._tasks.append(task)
    
    async def _stop(self) -> None:
        """Stop the intake agent"""
        self.logger.info("Stopping Intake Agent")
        
        # Close any active calls
        for call_id in list(self.active_calls.keys()):
            await self._end_call(call_id)
    
    async def handle_message(self, message: Message) -> None:
        """Handle incoming messages"""
        if message.type == MessageType.CALL_INTAKE:
            await self._handle_intake_request(message)
        else:
            self.logger.warning(f"Received unexpected message type: {message.type}")
    
    async def _handle_intake_request(self, message: Message) -> None:
        """Process call intake request"""
        try:
            # Extract call information
            call_data = message.payload
            
            # Validate and create call metadata
            call_metadata = await self._create_call_metadata(call_data)
            
            # Store active call
            self.active_calls[call_metadata.call_id] = call_metadata
            
            # Generate greeting
            greeting = self._generate_greeting()
            
            # Send initial response
            await self._send_intake_response(call_metadata, greeting)
            
            # Collect customer information
            customer_info = await self._collect_customer_information(call_metadata)
            
            # Update metadata with collected information
            call_metadata.customer_name = customer_info.get("name")
            call_metadata.account_number = customer_info.get("account_number")
            call_metadata.call_reason = customer_info.get("reason")
            
            # Determine priority based on reason
            call_metadata.priority = self._determine_priority(call_metadata.call_reason)
            
            # Send to transcription agent
            await self._forward_to_transcription(call_metadata)
            
        except ValidationException as e:
            self.logger.error(f"Validation error in intake: {e}")
            await self._send_error_response(message, str(e))
        except Exception as e:
            self.logger.error(f"Error handling intake request: {e}")
            await self._send_error_response(message, "Failed to process intake request")
    
    async def _create_call_metadata(self, call_data: Dict[str, Any]) -> CallMetadata:
        """Create and validate call metadata"""
        try:
            # Generate call ID if not provided
            if "call_id" not in call_data:
                call_data["call_id"] = self._generate_call_id()
            
            # Create metadata object
            metadata = CallMetadata(**call_data)
            
            self.logger.info(f"Created call metadata for call {metadata.call_id}")
            return metadata
            
        except Exception as e:
            raise ValidationException(f"Invalid call data: {e}")
    
    def _generate_call_id(self) -> str:
        """Generate unique call ID"""
        import uuid
        return f"CALL-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"
    
    def _generate_greeting(self) -> str:
        """Generate personalized greeting"""
        return self.greeting_template.format(
            company_name=self.company_name,
            agent_name=self.name
        )
    
    async def _collect_customer_information(self, metadata: CallMetadata) -> Dict[str, Any]:
        """Collect customer information through prompts"""
        customer_info = {}
        
        # Simulate collecting information (in real implementation, this would interact with telephony)
        prompts = [
            ("May I have your name, please?", "name"),
            ("Could you provide your account number?", "account_number"),
            ("How may I assist you today?", "reason")
        ]
        
        for prompt, field in prompts:
            # In real implementation, this would send prompt and wait for response
            self.logger.debug(f"Prompt: {prompt}")
            # Simulate response
            customer_info[field] = f"Sample {field}"
        
        return customer_info
    
    def _determine_priority(self, reason: Optional[str]) -> str:
        """Determine call priority based on reason"""
        if not reason:
            return "normal"
        
        reason_lower = reason.lower()
        
        # Urgent keywords
        urgent_keywords = ["emergency", "urgent", "critical", "immediate"]
        if any(keyword in reason_lower for keyword in urgent_keywords):
            return "urgent"
        
        # High priority keywords
        high_keywords = ["complaint", "escalation", "billing issue", "service down"]
        if any(keyword in reason_lower for keyword in high_keywords):
            return "high"
        
        # Low priority keywords
        low_keywords = ["information", "general inquiry", "question"]
        if any(keyword in reason_lower for keyword in low_keywords):
            return "low"
        
        return "normal"
    
    async def _send_intake_response(self, metadata: CallMetadata, greeting: str) -> None:
        """Send intake response"""
        response = Message(
            type=MessageType.CALL_INTAKE,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": metadata.call_id,
                "greeting": greeting,
                "status": "intake_started",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        await self.send_message(response)
    
    async def _forward_to_transcription(self, metadata: CallMetadata) -> None:
        """Forward call to transcription agent"""
        message = Message(
            type=MessageType.TRANSCRIPTION,
            sender=self.name,
            recipient="TranscriptionAgent",
            payload={
                "call_id": metadata.call_id,
                "metadata": metadata.dict(),
                "audio_stream": "audio_stream_url",  # In real implementation, this would be actual audio stream
                "start_transcription": True
            }
        )
        
        await self.send_message(message)
        self.logger.info(f"Forwarded call {metadata.call_id} to transcription")
    
    async def _send_error_response(self, original_message: Message, error: str) -> None:
        """Send error response"""
        response = Message(
            type=MessageType.ERROR,
            sender=self.name,
            recipient=original_message.sender,
            payload={
                "error": error,
                "original_message_id": original_message.id
            },
            reply_to=original_message.id
        )
        
        await self.send_message(response)
    
    async def _monitor_incoming_calls(self) -> None:
        """Monitor for incoming calls (telephony integration)"""
        while self._running:
            try:
                # In real implementation, this would listen for incoming calls
                await asyncio.sleep(1)
                
            except Exception as e:
                self.logger.error(f"Error monitoring calls: {e}")
    
    async def _initialize_telephony(self) -> None:
        """Initialize telephony connection"""
        # In real implementation, this would set up Twilio or other telephony service
        self.logger.info("Telephony initialization would happen here")
    
    async def _end_call(self, call_id: str) -> None:
        """End an active call"""
        if call_id in self.active_calls:
            del self.active_calls[call_id]
            self.logger.info(f"Ended call {call_id}")
    
    def _load_intake_scripts(self) -> Dict[str, str]:
        """Load predefined intake scripts"""
        return {
            "greeting": self.greeting_template,
            "name_prompt": "May I have your name, please?",
            "account_prompt": "Could you provide your account number?",
            "reason_prompt": "How may I assist you today?",
            "hold_message": "Please hold while I connect you to the right department.",
            "thank_you": "Thank you for calling. Have a great day!"
        }
    
    def get_active_calls(self) -> Dict[str, Dict[str, Any]]:
        """Get information about active calls"""
        return {
            call_id: metadata.dict() 
            for call_id, metadata in self.active_calls.items()
        }