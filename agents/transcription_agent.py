"""Transcription Agent - Converts audio to text with speaker diarization"""

import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum
import json
from dataclasses import dataclass

from core import BaseAgent, AgentConfig, get_logger
from core.base_agent import Message, MessageType
from core.exceptions import TranscriptionException


class TranscriptionProvider(str, Enum):
    """Supported transcription providers"""
    DEEPGRAM = "deepgram"
    WHISPER = "whisper"
    GOOGLE = "google"


@dataclass
class TranscriptionSegment:
    """Represents a transcribed segment with speaker information"""
    text: str
    speaker: str
    start_time: float
    end_time: float
    confidence: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "speaker": self.speaker,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "confidence": self.confidence
        }


class TranscriptionAgent(BaseAgent):
    """Agent responsible for converting speech to text with speaker diarization"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.provider = TranscriptionProvider(
            config.custom_config.get("provider", "deepgram")
        )
        self.language = config.custom_config.get("language", "en")
        self.enable_diarization = config.custom_config.get("enable_diarization", True)
        self.active_transcriptions: Dict[str, Dict[str, Any]] = {}
        self.transcription_client = None
        
    async def _initialize(self) -> None:
        """Initialize the transcription agent"""
        self.logger.info(f"Initializing Transcription Agent with provider: {self.provider}")
        
        # Initialize transcription provider
        await self._initialize_provider()
        
        # Load language models if needed
        if self.provider == TranscriptionProvider.WHISPER:
            await self._load_whisper_model()
    
    async def _initialize_provider(self) -> None:
        """Initialize the transcription provider"""
        try:
            if self.provider == TranscriptionProvider.DEEPGRAM:
                await self._initialize_deepgram()
            elif self.provider == TranscriptionProvider.WHISPER:
                await self._initialize_whisper()
            elif self.provider == TranscriptionProvider.GOOGLE:
                await self._initialize_google()
            else:
                raise TranscriptionException(f"Unsupported provider: {self.provider}")
                
        except Exception as e:
            raise TranscriptionException(f"Failed to initialize provider: {e}")
    
    async def _initialize_deepgram(self) -> None:
        """Initialize Deepgram client"""
        try:
            # Import would be conditional based on installation
            # from deepgram import Deepgram
            
            api_key = self.config.custom_config.get("deepgram_api_key")
            if not api_key:
                self.logger.warning("Deepgram API key not configured, using mock mode")
                self.transcription_client = MockDeepgramClient()
            else:
                # self.transcription_client = Deepgram(api_key)
                self.transcription_client = MockDeepgramClient()  # Using mock for now
                
            self.logger.info("Deepgram client initialized")
            
        except Exception as e:
            raise TranscriptionException(f"Failed to initialize Deepgram: {e}")
    
    async def _initialize_whisper(self) -> None:
        """Initialize Whisper model"""
        try:
            # import whisper
            # self.transcription_client = whisper.load_model("base")
            self.transcription_client = MockWhisperClient()  # Using mock for now
            self.logger.info("Whisper model initialized")
            
        except Exception as e:
            raise TranscriptionException(f"Failed to initialize Whisper: {e}")
    
    async def _initialize_google(self) -> None:
        """Initialize Google Speech-to-Text"""
        # Implementation for Google Speech-to-Text
        self.transcription_client = MockGoogleClient()
        self.logger.info("Google Speech-to-Text initialized")
    
    async def _load_whisper_model(self) -> None:
        """Load Whisper model"""
        model_size = self.config.custom_config.get("whisper_model_size", "base")
        self.logger.info(f"Loading Whisper model: {model_size}")
        # Model loading would happen here
    
    async def _start(self) -> None:
        """Start the transcription agent"""
        self.logger.info("Starting Transcription Agent")
        
        # Start processing loop for active transcriptions
        task = asyncio.create_task(self._process_transcriptions())
        self._tasks.append(task)
    
    async def _stop(self) -> None:
        """Stop the transcription agent"""
        self.logger.info("Stopping Transcription Agent")
        
        # Stop all active transcriptions
        for call_id in list(self.active_transcriptions.keys()):
            await self._stop_transcription(call_id)
    
    async def handle_message(self, message: Message) -> None:
        """Handle incoming messages"""
        if message.type == MessageType.TRANSCRIPTION:
            await self._handle_transcription_request(message)
        else:
            self.logger.warning(f"Received unexpected message type: {message.type}")
    
    async def _handle_transcription_request(self, message: Message) -> None:
        """Process transcription request"""
        try:
            call_id = message.payload.get("call_id")
            
            if message.payload.get("start_transcription"):
                await self._start_transcription(call_id, message.payload)
            elif message.payload.get("stop_transcription"):
                await self._stop_transcription(call_id)
            elif message.payload.get("audio_chunk"):
                await self._process_audio_chunk(call_id, message.payload["audio_chunk"])
            else:
                self.logger.warning(f"Unknown transcription request for call {call_id}")
                
        except Exception as e:
            self.logger.error(f"Error handling transcription request: {e}")
            await self._send_error_response(message, str(e))
    
    async def _start_transcription(self, call_id: str, config: Dict[str, Any]) -> None:
        """Start transcription for a call"""
        self.logger.info(f"Starting transcription for call {call_id}")
        
        # Initialize transcription session
        self.active_transcriptions[call_id] = {
            "call_id": call_id,
            "metadata": config.get("metadata", {}),
            "start_time": datetime.utcnow(),
            "segments": [],
            "full_transcript": "",
            "speakers": set(),
            "status": "active"
        }
        
        # Start real-time transcription
        if self.provider == TranscriptionProvider.DEEPGRAM:
            await self._start_deepgram_stream(call_id)
        elif self.provider == TranscriptionProvider.WHISPER:
            await self._start_whisper_stream(call_id)
        
        # Send confirmation
        await self._send_transcription_started(call_id)
    
    async def _stop_transcription(self, call_id: str) -> None:
        """Stop transcription for a call"""
        if call_id in self.active_transcriptions:
            self.logger.info(f"Stopping transcription for call {call_id}")
            
            # Mark as completed
            self.active_transcriptions[call_id]["status"] = "completed"
            self.active_transcriptions[call_id]["end_time"] = datetime.utcnow()
            
            # Send final transcript
            await self._send_final_transcript(call_id)
            
            # Clean up
            del self.active_transcriptions[call_id]
    
    async def _process_audio_chunk(self, call_id: str, audio_chunk: bytes) -> None:
        """Process an audio chunk"""
        if call_id not in self.active_transcriptions:
            self.logger.warning(f"No active transcription for call {call_id}")
            return
        
        try:
            # Transcribe audio chunk
            segment = await self._transcribe_chunk(audio_chunk, call_id)
            
            if segment:
                # Add to segments
                self.active_transcriptions[call_id]["segments"].append(segment)
                
                # Update full transcript
                self.active_transcriptions[call_id]["full_transcript"] += f" {segment.text}"
                
                # Track speakers
                self.active_transcriptions[call_id]["speakers"].add(segment.speaker)
                
                # Send real-time update
                await self._send_transcription_update(call_id, segment)
                
        except Exception as e:
            self.logger.error(f"Error processing audio chunk: {e}")
    
    async def _transcribe_chunk(self, audio_chunk: bytes, call_id: str) -> Optional[TranscriptionSegment]:
        """Transcribe an audio chunk"""
        try:
            if self.provider == TranscriptionProvider.DEEPGRAM:
                return await self._transcribe_with_deepgram(audio_chunk)
            elif self.provider == TranscriptionProvider.WHISPER:
                return await self._transcribe_with_whisper(audio_chunk)
            elif self.provider == TranscriptionProvider.GOOGLE:
                return await self._transcribe_with_google(audio_chunk)
                
        except Exception as e:
            self.logger.error(f"Transcription error: {e}")
            return None
    
    async def _transcribe_with_deepgram(self, audio_chunk: bytes) -> TranscriptionSegment:
        """Transcribe using Deepgram"""
        # Mock implementation
        return TranscriptionSegment(
            text="This is a sample transcription from Deepgram",
            speaker="Speaker 1",
            start_time=0.0,
            end_time=2.0,
            confidence=0.95
        )
    
    async def _transcribe_with_whisper(self, audio_chunk: bytes) -> TranscriptionSegment:
        """Transcribe using Whisper"""
        # Mock implementation
        return TranscriptionSegment(
            text="This is a sample transcription from Whisper",
            speaker="Speaker 1",
            start_time=0.0,
            end_time=2.0,
            confidence=0.92
        )
    
    async def _transcribe_with_google(self, audio_chunk: bytes) -> TranscriptionSegment:
        """Transcribe using Google Speech-to-Text"""
        # Mock implementation
        return TranscriptionSegment(
            text="This is a sample transcription from Google",
            speaker="Speaker 1",
            start_time=0.0,
            end_time=2.0,
            confidence=0.93
        )
    
    async def _start_deepgram_stream(self, call_id: str) -> None:
        """Start Deepgram streaming transcription"""
        # Implementation for Deepgram streaming
        self.logger.info(f"Starting Deepgram stream for call {call_id}")
    
    async def _start_whisper_stream(self, call_id: str) -> None:
        """Start Whisper streaming transcription"""
        # Implementation for Whisper streaming
        self.logger.info(f"Starting Whisper stream for call {call_id}")
    
    async def _send_transcription_started(self, call_id: str) -> None:
        """Send transcription started notification"""
        message = Message(
            type=MessageType.TRANSCRIPTION,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": call_id,
                "status": "transcription_started",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        await self.send_message(message)
    
    async def _send_transcription_update(self, call_id: str, segment: TranscriptionSegment) -> None:
        """Send real-time transcription update"""
        # Send to summarization agent
        message = Message(
            type=MessageType.SUMMARY,
            sender=self.name,
            recipient="SummarizationAgent",
            payload={
                "call_id": call_id,
                "segment": segment.to_dict(),
                "update_type": "real_time"
            }
        )
        
        await self.send_message(message)
    
    async def _send_final_transcript(self, call_id: str) -> None:
        """Send final transcript"""
        transcription_data = self.active_transcriptions[call_id]
        
        # Send to summarization agent
        message = Message(
            type=MessageType.SUMMARY,
            sender=self.name,
            recipient="SummarizationAgent",
            payload={
                "call_id": call_id,
                "full_transcript": transcription_data["full_transcript"],
                "segments": [s.to_dict() for s in transcription_data["segments"]],
                "speakers": list(transcription_data["speakers"]),
                "duration": (
                    transcription_data["end_time"] - transcription_data["start_time"]
                ).total_seconds(),
                "update_type": "final"
            }
        )
        
        await self.send_message(message)
        
        self.logger.info(f"Sent final transcript for call {call_id}")
    
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
    
    async def _process_transcriptions(self) -> None:
        """Process active transcriptions"""
        while self._running:
            try:
                # Check for stale transcriptions
                current_time = datetime.utcnow()
                for call_id, data in list(self.active_transcriptions.items()):
                    if data["status"] == "active":
                        duration = (current_time - data["start_time"]).total_seconds()
                        if duration > self.config.timeout_seconds:
                            self.logger.warning(f"Transcription timeout for call {call_id}")
                            await self._stop_transcription(call_id)
                
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error in transcription processing loop: {e}")


# Mock clients for testing
class MockDeepgramClient:
    """Mock Deepgram client for testing"""
    async def transcribe(self, audio: bytes) -> Dict[str, Any]:
        return {"text": "Mock transcription", "confidence": 0.95}


class MockWhisperClient:
    """Mock Whisper client for testing"""
    def transcribe(self, audio: bytes) -> Dict[str, Any]:
        return {"text": "Mock transcription", "segments": []}


class MockGoogleClient:
    """Mock Google client for testing"""
    async def transcribe(self, audio: bytes) -> Dict[str, Any]:
        return {"transcript": "Mock transcription", "confidence": 0.93}