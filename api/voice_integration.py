"""Voice Integration with Twilio and Deepgram"""

import asyncio
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import json
import base64
import io
import wave

from twilio.rest import Client as TwilioClient
from twilio.twiml import VoiceResponse
from fastapi import WebSocket, WebSocketDisconnect
import websockets
from deepgram import Deepgram
import httpx

from core import get_logger
from core.base_agent import Message, MessageType
from core.exceptions import CommunicationException


class TwilioVoiceHandler:
    """Handle Twilio voice calls and webhooks"""
    
    def __init__(self, account_sid: str, auth_token: str, phone_number: str):
        self.account_sid = account_sid
        self.auth_token = auth_token
        self.phone_number = phone_number
        self.client = TwilioClient(account_sid, auth_token)
        self.logger = get_logger(__name__)
        
        # Active call sessions
        self.active_calls: Dict[str, Dict[str, Any]] = {}
    
    def create_call(
        self,
        to_number: str,
        webhook_url: str,
        call_data: Dict[str, Any] = None
    ) -> str:
        """Create outbound call"""
        try:
            call = self.client.calls.create(
                to=to_number,
                from_=self.phone_number,
                url=f"{webhook_url}/voice/handle",
                status_callback=f"{webhook_url}/voice/status",
                record=True,
                machine_detection="DetectMessageEnd"
            )
            
            # Store call session
            self.active_calls[call.sid] = {
                "call_sid": call.sid,
                "to_number": to_number,
                "status": "initiated",
                "created_at": datetime.utcnow(),
                "data": call_data or {}
            }
            
            self.logger.info(f"Created outbound call {call.sid} to {to_number}")
            return call.sid
            
        except Exception as e:
            self.logger.error(f"Failed to create call: {e}")
            raise CommunicationException(f"Call creation failed: {e}")
    
    def handle_incoming_call(self, request_data: Dict[str, Any]) -> str:
        """Handle incoming call webhook"""
        call_sid = request_data.get("CallSid")
        caller_number = request_data.get("From")
        called_number = request_data.get("To")
        
        self.logger.info(f"Incoming call {call_sid} from {caller_number}")
        
        # Store call session
        self.active_calls[call_sid] = {
            "call_sid": call_sid,
            "caller_number": caller_number,
            "called_number": called_number,
            "status": "ringing",
            "created_at": datetime.utcnow(),
            "direction": "inbound"
        }
        
        # Create TwiML response
        response = VoiceResponse()
        
        # Play greeting
        response.say(
            "Thank you for calling AI Call Center. Please hold while we connect you to an agent.",
            voice="alice"
        )
        
        # Start recording
        response.record(
            action="/voice/recording",
            method="POST",
            max_length=3600,
            timeout=10,
            play_beep=False,
            transcribe=False
        )
        
        # Connect to streaming service
        response.connect().stream(
            url=f"wss://your-domain.com/voice/stream/{call_sid}"
        )
        
        return str(response)
    
    def handle_call_status(self, request_data: Dict[str, Any]) -> None:
        """Handle call status updates"""
        call_sid = request_data.get("CallSid")
        status = request_data.get("CallStatus")
        duration = request_data.get("CallDuration")
        
        if call_sid in self.active_calls:
            self.active_calls[call_sid]["status"] = status
            
            if status in ["completed", "failed", "canceled"]:
                self.active_calls[call_sid]["ended_at"] = datetime.utcnow()
                self.active_calls[call_sid]["duration"] = duration
                
                self.logger.info(f"Call {call_sid} ended with status {status}")
                
                # Clean up after some time
                asyncio.create_task(self._cleanup_call(call_sid, delay=300))
    
    def handle_recording(self, request_data: Dict[str, Any]) -> str:
        """Handle call recording webhook"""
        call_sid = request_data.get("CallSid")
        recording_url = request_data.get("RecordingUrl")
        recording_sid = request_data.get("RecordingSid")
        
        if call_sid in self.active_calls:
            self.active_calls[call_sid]["recording_url"] = recording_url
            self.active_calls[call_sid]["recording_sid"] = recording_sid
        
        self.logger.info(f"Recording completed for call {call_sid}")
        
        # Continue call flow
        response = VoiceResponse()
        response.hangup()
        return str(response)
    
    async def _cleanup_call(self, call_sid: str, delay: int = 0) -> None:
        """Clean up call session after delay"""
        if delay > 0:
            await asyncio.sleep(delay)
        
        if call_sid in self.active_calls:
            del self.active_calls[call_sid]
            self.logger.info(f"Cleaned up call session {call_sid}")
    
    def get_call_info(self, call_sid: str) -> Optional[Dict[str, Any]]:
        """Get call information"""
        return self.active_calls.get(call_sid)
    
    def end_call(self, call_sid: str) -> bool:
        """End an active call"""
        try:
            call = self.client.calls(call_sid)
            call.update(status="completed")
            
            if call_sid in self.active_calls:
                self.active_calls[call_sid]["status"] = "completed"
                self.active_calls[call_sid]["ended_at"] = datetime.utcnow()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to end call {call_sid}: {e}")
            return False


class DeepgramTranscriptionService:
    """Real-time transcription service using Deepgram"""
    
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.deepgram = Deepgram(api_key)
        self.logger = get_logger(__name__)
        
        # Active transcription sessions
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
    
    async def start_transcription(
        self,
        call_id: str,
        websocket: WebSocket,
        language: str = "en",
        model: str = "nova-2"
    ) -> None:
        """Start real-time transcription"""
        try:
            # Deepgram WebSocket connection
            deepgram_ws = await self.deepgram.transcription.live({
                "language": language,
                "model": model,
                "smart_format": True,
                "interim_results": True,
                "diarize": True,
                "punctuate": True,
                "utterance_end_ms": 1000,
                "vad_events": True
            })
            
            # Store session
            self.active_sessions[call_id] = {
                "call_id": call_id,
                "deepgram_ws": deepgram_ws,
                "client_ws": websocket,
                "started_at": datetime.utcnow(),
                "transcript_buffer": []
            }
            
            # Set up Deepgram event handlers
            deepgram_ws.on("transcript", self._handle_transcript)
            deepgram_ws.on("utterance_end", self._handle_utterance_end)
            deepgram_ws.on("error", self._handle_error)
            
            self.logger.info(f"Started transcription session for call {call_id}")
            
        except Exception as e:
            self.logger.error(f"Failed to start transcription: {e}")
            raise CommunicationException(f"Transcription start failed: {e}")
    
    async def process_audio(self, call_id: str, audio_data: bytes) -> None:
        """Process incoming audio data"""
        if call_id in self.active_sessions:
            session = self.active_sessions[call_id]
            deepgram_ws = session["deepgram_ws"]
            
            # Send audio to Deepgram
            await deepgram_ws.send(audio_data)
    
    async def _handle_transcript(self, data: Dict[str, Any]) -> None:
        """Handle transcript results from Deepgram"""
        try:
            transcript = data.get("alternatives", [{}])[0].get("transcript", "")
            confidence = data.get("alternatives", [{}])[0].get("confidence", 0)
            is_final = data.get("is_final", False)
            
            if transcript.strip():
                # Find the session for this transcript
                for call_id, session in self.active_sessions.items():
                    # Send transcript to client
                    await session["client_ws"].send_json({
                        "type": "transcript",
                        "call_id": call_id,
                        "transcript": transcript,
                        "confidence": confidence,
                        "is_final": is_final,
                        "timestamp": datetime.utcnow().isoformat()
                    })
                    
                    # Store in buffer if final
                    if is_final:
                        session["transcript_buffer"].append({
                            "text": transcript,
                            "confidence": confidence,
                            "timestamp": datetime.utcnow()
                        })
                    
                    break
                    
        except Exception as e:
            self.logger.error(f"Error handling transcript: {e}")
    
    async def _handle_utterance_end(self, data: Dict[str, Any]) -> None:
        """Handle utterance end events"""
        # Process completed utterances
        pass
    
    async def _handle_error(self, error: Dict[str, Any]) -> None:
        """Handle Deepgram errors"""
        self.logger.error(f"Deepgram error: {error}")
    
    async def stop_transcription(self, call_id: str) -> Dict[str, Any]:
        """Stop transcription and return final transcript"""
        if call_id not in self.active_sessions:
            return {"error": "No active session"}
        
        session = self.active_sessions[call_id]
        
        try:
            # Close Deepgram connection
            await session["deepgram_ws"].finish()
            
            # Compile final transcript
            full_transcript = " ".join([
                item["text"] for item in session["transcript_buffer"]
            ])
            
            transcript_segments = session["transcript_buffer"]
            
            # Clean up session
            del self.active_sessions[call_id]
            
            self.logger.info(f"Stopped transcription for call {call_id}")
            
            return {
                "call_id": call_id,
                "full_transcript": full_transcript,
                "segments": transcript_segments,
                "duration": (datetime.utcnow() - session["started_at"]).total_seconds()
            }
            
        except Exception as e:
            self.logger.error(f"Error stopping transcription: {e}")
            return {"error": str(e)}


class VoiceStreamHandler:
    """Handle real-time voice streaming"""
    
    def __init__(
        self,
        twilio_handler: TwilioVoiceHandler,
        transcription_service: DeepgramTranscriptionService,
        message_callback: Optional[Callable] = None
    ):
        self.twilio_handler = twilio_handler
        self.transcription_service = transcription_service
        self.message_callback = message_callback
        self.logger = get_logger(__name__)
        
        # Active streams
        self.active_streams: Dict[str, WebSocket] = {}
    
    async def handle_stream(self, websocket: WebSocket, call_id: str) -> None:
        """Handle WebSocket stream for a call"""
        await websocket.accept()
        
        try:
            self.active_streams[call_id] = websocket
            
            # Start transcription
            await self.transcription_service.start_transcription(call_id, websocket)
            
            self.logger.info(f"Started voice stream for call {call_id}")
            
            # Process incoming messages
            async for message in websocket.iter_json():
                await self._process_stream_message(call_id, message)
                
        except WebSocketDisconnect:
            self.logger.info(f"WebSocket disconnected for call {call_id}")
        except Exception as e:
            self.logger.error(f"Error in voice stream: {e}")
        finally:
            # Clean up
            await self._cleanup_stream(call_id)
    
    async def _process_stream_message(self, call_id: str, message: Dict[str, Any]) -> None:
        """Process incoming stream message"""
        msg_type = message.get("type")
        
        if msg_type == "audio":
            # Decode audio data
            audio_data = base64.b64decode(message.get("data", ""))
            
            # Send to transcription service
            await self.transcription_service.process_audio(call_id, audio_data)
            
        elif msg_type == "start":
            self.logger.info(f"Audio stream started for call {call_id}")
            
        elif msg_type == "stop":
            self.logger.info(f"Audio stream stopped for call {call_id}")
            
            # Stop transcription
            result = await self.transcription_service.stop_transcription(call_id)
            
            # Send final transcript via callback
            if self.message_callback and result.get("full_transcript"):
                await self.message_callback(Message(
                    type=MessageType.TRANSCRIPTION,
                    sender="VoiceStreamHandler",
                    recipient="SummarizationAgent",
                    payload={
                        "call_id": call_id,
                        "full_transcript": result["full_transcript"],
                        "segments": result.get("segments", []),
                        "duration": result.get("duration", 0),
                        "update_type": "final"
                    }
                ))
    
    async def _cleanup_stream(self, call_id: str) -> None:
        """Clean up stream resources"""
        if call_id in self.active_streams:
            del self.active_streams[call_id]
        
        # Stop transcription if still active
        await self.transcription_service.stop_transcription(call_id)


class TextToSpeechService:
    """Text-to-speech service for AI responses"""
    
    def __init__(self, provider: str = "elevenlabs"):
        self.provider = provider
        self.logger = get_logger(__name__)
    
    async def synthesize_speech(
        self,
        text: str,
        voice_id: str = "default",
        speed: float = 1.0
    ) -> bytes:
        """Convert text to speech"""
        try:
            if self.provider == "elevenlabs":
                return await self._elevenlabs_tts(text, voice_id, speed)
            elif self.provider == "google":
                return await self._google_tts(text, voice_id, speed)
            else:
                # Mock TTS for testing
                return await self._mock_tts(text)
                
        except Exception as e:
            self.logger.error(f"TTS error: {e}")
            return b""  # Return empty bytes on error
    
    async def _elevenlabs_tts(self, text: str, voice_id: str, speed: float) -> bytes:
        """ElevenLabs TTS implementation"""
        # Implementation for ElevenLabs API
        # This would require API key and proper integration
        return b""  # Mock return
    
    async def _google_tts(self, text: str, voice_id: str, speed: float) -> bytes:
        """Google Cloud TTS implementation"""
        # Implementation for Google Cloud TTS
        return b""  # Mock return
    
    async def _mock_tts(self, text: str) -> bytes:
        """Mock TTS for testing"""
        # Generate a simple audio buffer (silence)
        duration = len(text) * 0.1  # Approximate duration
        sample_rate = 16000
        samples = int(duration * sample_rate)
        
        # Create WAV file in memory
        buffer = io.BytesIO()
        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2)  # 16-bit
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(b'\x00' * (samples * 2))  # Silence
        
        return buffer.getvalue()