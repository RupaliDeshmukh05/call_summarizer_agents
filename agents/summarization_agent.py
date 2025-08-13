"""Summarization Agent - Generates summaries and extracts key points using GPT"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
import json
from pydantic import BaseModel, Field

from core import BaseAgent, AgentConfig, get_logger
from core.base_agent import Message, MessageType
from core.exceptions import AgentException


class SummaryType(str, Enum):
    """Types of summaries"""
    REAL_TIME = "real_time"
    FINAL = "final"
    PERIODIC = "periodic"


class CallSummary(BaseModel):
    """Model for call summary"""
    call_id: str
    summary: str
    key_points: List[str]
    action_items: List[str]
    sentiment: str  # positive, neutral, negative
    topics: List[str]
    customer_issues: List[str]
    resolution_status: str  # resolved, pending, escalated
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    confidence_score: float = 0.0


class SummarizationAgent(BaseAgent):
    """Agent responsible for generating call summaries and extracting insights"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.openai_api_key = config.custom_config.get("openai_api_key")
        self.model = config.custom_config.get("model", "gpt-4-turbo-preview")
        self.max_summary_length = config.custom_config.get("max_summary_length", 500)
        self.active_summaries: Dict[str, Dict[str, Any]] = {}
        self.summary_history: Dict[str, List[CallSummary]] = {}
        
    async def _initialize(self) -> None:
        """Initialize the summarization agent"""
        self.logger.info("Initializing Summarization Agent")
        
        # Initialize OpenAI client
        await self._initialize_openai()
        
        # Load prompt templates
        self.prompt_templates = self._load_prompt_templates()
    
    async def _initialize_openai(self) -> None:
        """Initialize OpenAI client"""
        try:
            if self.openai_api_key:
                # import openai
                # openai.api_key = self.openai_api_key
                self.logger.info("OpenAI client initialized")
            else:
                self.logger.warning("OpenAI API key not configured, using mock mode")
        except Exception as e:
            raise AgentException(f"Failed to initialize OpenAI: {e}")
    
    def _load_prompt_templates(self) -> Dict[str, str]:
        """Load prompt templates for different summary types"""
        return {
            "real_time_summary": """
                Analyze this conversation segment and provide:
                1. A brief summary (max 100 words)
                2. Any key points mentioned
                3. Customer sentiment
                
                Conversation: {transcript}
                
                Format your response as JSON with keys: summary, key_points, sentiment
            """,
            
            "final_summary": """
                Analyze this complete call transcript and provide:
                1. Executive summary (max {max_length} words)
                2. Key points discussed (bullet points)
                3. Action items identified
                4. Customer issues mentioned
                5. Topics covered
                6. Overall sentiment
                7. Resolution status
                
                Full Transcript: {transcript}
                Call Metadata: {metadata}
                
                Format your response as JSON with keys: 
                summary, key_points, action_items, customer_issues, topics, sentiment, resolution_status
            """,
            
            "extract_action_items": """
                Extract all action items from this conversation.
                Include who is responsible and any deadlines mentioned.
                
                Transcript: {transcript}
                
                Return as JSON array of action items with keys: description, responsible_party, deadline
            """,
            
            "sentiment_analysis": """
                Analyze the customer sentiment throughout this conversation.
                Consider tone, language, and satisfaction indicators.
                
                Transcript: {transcript}
                
                Return JSON with keys: overall_sentiment, sentiment_progression, satisfaction_score (0-10)
            """
        }
    
    async def _start(self) -> None:
        """Start the summarization agent"""
        self.logger.info("Starting Summarization Agent")
        
        # Start periodic summary generation
        task = asyncio.create_task(self._generate_periodic_summaries())
        self._tasks.append(task)
    
    async def _stop(self) -> None:
        """Stop the summarization agent"""
        self.logger.info("Stopping Summarization Agent")
        
        # Generate final summaries for all active calls
        for call_id in list(self.active_summaries.keys()):
            await self._generate_final_summary(call_id)
    
    async def handle_message(self, message: Message) -> None:
        """Handle incoming messages"""
        if message.type == MessageType.SUMMARY:
            await self._handle_summary_request(message)
        else:
            self.logger.warning(f"Received unexpected message type: {message.type}")
    
    async def _handle_summary_request(self, message: Message) -> None:
        """Process summary request"""
        try:
            call_id = message.payload.get("call_id")
            update_type = message.payload.get("update_type", "real_time")
            
            if call_id not in self.active_summaries:
                self.active_summaries[call_id] = {
                    "call_id": call_id,
                    "transcript_segments": [],
                    "full_transcript": "",
                    "metadata": message.payload.get("metadata", {}),
                    "start_time": datetime.utcnow()
                }
            
            if update_type == "real_time":
                await self._process_real_time_update(call_id, message.payload)
            elif update_type == "final":
                await self._process_final_transcript(call_id, message.payload)
            elif update_type == "periodic":
                await self._generate_periodic_summary(call_id)
            
        except Exception as e:
            self.logger.error(f"Error handling summary request: {e}")
            await self._send_error_response(message, str(e))
    
    async def _process_real_time_update(self, call_id: str, payload: Dict[str, Any]) -> None:
        """Process real-time transcription update"""
        segment = payload.get("segment", {})
        
        # Add segment to active summary
        self.active_summaries[call_id]["transcript_segments"].append(segment)
        
        # Update full transcript
        if segment.get("text"):
            self.active_summaries[call_id]["full_transcript"] += f" {segment['text']}"
        
        # Generate real-time insights every N segments
        if len(self.active_summaries[call_id]["transcript_segments"]) % 5 == 0:
            await self._generate_real_time_summary(call_id)
    
    async def _process_final_transcript(self, call_id: str, payload: Dict[str, Any]) -> None:
        """Process final transcript and generate comprehensive summary"""
        # Update with final transcript
        self.active_summaries[call_id]["full_transcript"] = payload.get("full_transcript", "")
        self.active_summaries[call_id]["segments"] = payload.get("segments", [])
        self.active_summaries[call_id]["speakers"] = payload.get("speakers", [])
        self.active_summaries[call_id]["duration"] = payload.get("duration", 0)
        
        # Generate final summary
        await self._generate_final_summary(call_id)
    
    async def _generate_real_time_summary(self, call_id: str) -> None:
        """Generate real-time summary for recent segments"""
        try:
            call_data = self.active_summaries[call_id]
            
            # Get last 5 segments
            recent_segments = call_data["transcript_segments"][-5:]
            recent_text = " ".join([s.get("text", "") for s in recent_segments])
            
            if not recent_text.strip():
                return
            
            # Generate summary using GPT
            summary_data = await self._call_gpt(
                self.prompt_templates["real_time_summary"].format(
                    transcript=recent_text
                )
            )
            
            # Create summary object
            summary = CallSummary(
                call_id=call_id,
                summary=summary_data.get("summary", ""),
                key_points=summary_data.get("key_points", []),
                action_items=[],
                sentiment=summary_data.get("sentiment", "neutral"),
                topics=[],
                customer_issues=[],
                resolution_status="pending"
            )
            
            # Send update
            await self._send_summary_update(call_id, summary, SummaryType.REAL_TIME)
            
        except Exception as e:
            self.logger.error(f"Error generating real-time summary: {e}")
    
    async def _generate_final_summary(self, call_id: str) -> None:
        """Generate comprehensive final summary"""
        try:
            call_data = self.active_summaries[call_id]
            full_transcript = call_data.get("full_transcript", "")
            
            if not full_transcript.strip():
                self.logger.warning(f"No transcript available for call {call_id}")
                return
            
            # Generate comprehensive summary
            summary_data = await self._call_gpt(
                self.prompt_templates["final_summary"].format(
                    transcript=full_transcript,
                    metadata=json.dumps(call_data.get("metadata", {})),
                    max_length=self.max_summary_length
                )
            )
            
            # Extract action items
            action_items_data = await self._call_gpt(
                self.prompt_templates["extract_action_items"].format(
                    transcript=full_transcript
                )
            )
            
            # Analyze sentiment
            sentiment_data = await self._call_gpt(
                self.prompt_templates["sentiment_analysis"].format(
                    transcript=full_transcript
                )
            )
            
            # Create final summary
            summary = CallSummary(
                call_id=call_id,
                summary=summary_data.get("summary", ""),
                key_points=summary_data.get("key_points", []),
                action_items=[item["description"] for item in action_items_data.get("items", [])],
                sentiment=sentiment_data.get("overall_sentiment", "neutral"),
                topics=summary_data.get("topics", []),
                customer_issues=summary_data.get("customer_issues", []),
                resolution_status=summary_data.get("resolution_status", "pending"),
                confidence_score=0.95
            )
            
            # Store in history
            if call_id not in self.summary_history:
                self.summary_history[call_id] = []
            self.summary_history[call_id].append(summary)
            
            # Send to quality scoring agent
            await self._send_to_quality_scoring(call_id, summary)
            
            # Send final summary update
            await self._send_summary_update(call_id, summary, SummaryType.FINAL)
            
            # Clean up
            del self.active_summaries[call_id]
            
        except Exception as e:
            self.logger.error(f"Error generating final summary: {e}")
    
    async def _generate_periodic_summary(self, call_id: str) -> None:
        """Generate periodic summary for ongoing call"""
        try:
            call_data = self.active_summaries.get(call_id)
            if not call_data:
                return
            
            transcript = call_data.get("full_transcript", "")
            if not transcript.strip():
                return
            
            # Generate periodic summary
            summary_data = await self._call_gpt(
                self.prompt_templates["real_time_summary"].format(
                    transcript=transcript[-2000:]  # Last 2000 characters
                )
            )
            
            summary = CallSummary(
                call_id=call_id,
                summary=summary_data.get("summary", ""),
                key_points=summary_data.get("key_points", []),
                action_items=[],
                sentiment=summary_data.get("sentiment", "neutral"),
                topics=[],
                customer_issues=[],
                resolution_status="in_progress"
            )
            
            await self._send_summary_update(call_id, summary, SummaryType.PERIODIC)
            
        except Exception as e:
            self.logger.error(f"Error generating periodic summary: {e}")
    
    async def _generate_periodic_summaries(self) -> None:
        """Periodically generate summaries for active calls"""
        while self._running:
            try:
                # Generate summaries every 30 seconds for active calls
                for call_id in list(self.active_summaries.keys()):
                    await self._generate_periodic_summary(call_id)
                
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in periodic summary generation: {e}")
    
    async def _call_gpt(self, prompt: str) -> Dict[str, Any]:
        """Call GPT API for text generation"""
        try:
            if self.openai_api_key:
                # Real GPT call would happen here
                # response = await openai.ChatCompletion.create(
                #     model=self.model,
                #     messages=[{"role": "user", "content": prompt}],
                #     temperature=0.7
                # )
                # return json.loads(response.choices[0].message.content)
                pass
            
            # Mock response for testing
            return {
                "summary": "Customer called regarding product issue. Agent provided troubleshooting steps.",
                "key_points": ["Product malfunction", "Troubleshooting attempted", "Issue resolved"],
                "action_items": ["Follow up in 24 hours", "Send replacement if issue persists"],
                "sentiment": "neutral",
                "topics": ["Technical Support", "Product Issue"],
                "customer_issues": ["Product not working as expected"],
                "resolution_status": "resolved",
                "overall_sentiment": "neutral",
                "items": [
                    {"description": "Follow up with customer", "responsible_party": "Agent", "deadline": "24 hours"}
                ]
            }
            
        except Exception as e:
            self.logger.error(f"Error calling GPT: {e}")
            return {}
    
    async def _send_summary_update(self, call_id: str, summary: CallSummary, summary_type: SummaryType) -> None:
        """Send summary update to system"""
        message = Message(
            type=MessageType.SUMMARY,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": call_id,
                "summary_type": summary_type.value,
                "summary": summary.dict(),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        await self.send_message(message)
        self.logger.info(f"Sent {summary_type.value} summary for call {call_id}")
    
    async def _send_to_quality_scoring(self, call_id: str, summary: CallSummary) -> None:
        """Send summary to quality scoring agent"""
        message = Message(
            type=MessageType.QUALITY_SCORE,
            sender=self.name,
            recipient="QualityScoringAgent",
            payload={
                "call_id": call_id,
                "summary": summary.dict(),
                "transcript": self.active_summaries[call_id].get("full_transcript", ""),
                "metadata": self.active_summaries[call_id].get("metadata", {})
            }
        )
        
        await self.send_message(message)
    
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
    
    def get_summary_history(self, call_id: str) -> List[Dict[str, Any]]:
        """Get summary history for a call"""
        summaries = self.summary_history.get(call_id, [])
        return [s.dict() for s in summaries]