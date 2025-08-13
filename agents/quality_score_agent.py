"""Quality Scoring Agent - Evaluates calls using structured rubric"""

import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, validator

from core import BaseAgent, AgentConfig, get_logger
from core.base_agent import Message, MessageType
from core.exceptions import AgentException


class QualityDimension(str, Enum):
    """Quality assessment dimensions"""
    GREETING = "greeting"
    IDENTITY_VERIFICATION = "identity_verification"
    ISSUE_UNDERSTANDING = "issue_understanding"
    SOLUTION_PROVIDED = "solution_provided"
    PROFESSIONALISM = "professionalism"
    EMPATHY = "empathy"
    COMPLIANCE = "compliance"
    CLOSURE = "closure"


class ScoreLevel(str, Enum):
    """Score levels"""
    EXCELLENT = "excellent"
    GOOD = "good"
    SATISFACTORY = "satisfactory"
    NEEDS_IMPROVEMENT = "needs_improvement"
    POOR = "poor"


class QualityScore(BaseModel):
    """Model for quality score"""
    dimension: QualityDimension
    score: int  # 0-100
    level: ScoreLevel
    notes: str
    
    @validator("score")
    def validate_score(cls, v):
        if not 0 <= v <= 100:
            raise ValueError("Score must be between 0 and 100")
        return v


class CallQualityAssessment(BaseModel):
    """Complete call quality assessment"""
    call_id: str
    overall_score: int  # 0-100
    overall_level: ScoreLevel
    dimension_scores: List[QualityScore]
    compliance_status: bool
    sentiment_score: float  # -1 to 1
    professionalism_score: float  # 0 to 1
    resolution_effectiveness: float  # 0 to 1
    customer_satisfaction_predicted: float  # 0 to 1
    strengths: List[str]
    areas_for_improvement: List[str]
    coaching_recommendations: List[str]
    assessed_at: datetime = Field(default_factory=datetime.utcnow)
    assessor: str = "AI Quality System"


class QualityScoringAgent(BaseAgent):
    """Agent responsible for evaluating call quality and compliance"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.scoring_rubric = self._initialize_rubric()
        self.compliance_rules = self._load_compliance_rules()
        self.assessments: Dict[str, CallQualityAssessment] = {}
        self.benchmark_scores = {
            "excellent": 90,
            "good": 75,
            "satisfactory": 60,
            "needs_improvement": 45,
            "poor": 0
        }
    
    def _initialize_rubric(self) -> Dict[QualityDimension, Dict[str, Any]]:
        """Initialize scoring rubric"""
        return {
            QualityDimension.GREETING: {
                "weight": 0.10,
                "criteria": {
                    "excellent": ["Warm greeting", "Company name mentioned", "Agent name provided", "Offer to help"],
                    "good": ["Greeting present", "Company mentioned", "Professional tone"],
                    "satisfactory": ["Basic greeting", "Identifies as support"],
                    "needs_improvement": ["Minimal greeting", "Rushed introduction"],
                    "poor": ["No greeting", "Unprofessional start"]
                }
            },
            QualityDimension.IDENTITY_VERIFICATION: {
                "weight": 0.15,
                "criteria": {
                    "excellent": ["Full verification completed", "Security questions asked", "Account confirmed"],
                    "good": ["Basic verification done", "Account number collected"],
                    "satisfactory": ["Name verification only"],
                    "needs_improvement": ["Incomplete verification"],
                    "poor": ["No verification attempted"]
                }
            },
            QualityDimension.ISSUE_UNDERSTANDING: {
                "weight": 0.15,
                "criteria": {
                    "excellent": ["Complete understanding", "Clarifying questions asked", "Issue summarized back"],
                    "good": ["Good understanding", "Some clarification sought"],
                    "satisfactory": ["Basic understanding demonstrated"],
                    "needs_improvement": ["Partial understanding", "Assumptions made"],
                    "poor": ["Misunderstood issue", "No clarification attempted"]
                }
            },
            QualityDimension.SOLUTION_PROVIDED: {
                "weight": 0.20,
                "criteria": {
                    "excellent": ["Complete solution", "Multiple options offered", "Follow-up scheduled"],
                    "good": ["Effective solution", "Clear next steps"],
                    "satisfactory": ["Basic solution provided"],
                    "needs_improvement": ["Partial solution", "Unclear resolution"],
                    "poor": ["No solution", "Issue unresolved"]
                }
            },
            QualityDimension.PROFESSIONALISM: {
                "weight": 0.10,
                "criteria": {
                    "excellent": ["Consistently professional", "Excellent communication", "Patient and courteous"],
                    "good": ["Professional throughout", "Clear communication"],
                    "satisfactory": ["Generally professional"],
                    "needs_improvement": ["Some unprofessional moments"],
                    "poor": ["Unprofessional behavior", "Poor communication"]
                }
            },
            QualityDimension.EMPATHY: {
                "weight": 0.10,
                "criteria": {
                    "excellent": ["High empathy shown", "Acknowledged feelings", "Personal touch"],
                    "good": ["Good empathy", "Understanding shown"],
                    "satisfactory": ["Basic empathy present"],
                    "needs_improvement": ["Limited empathy"],
                    "poor": ["No empathy", "Dismissive attitude"]
                }
            },
            QualityDimension.COMPLIANCE: {
                "weight": 0.10,
                "criteria": {
                    "excellent": ["All procedures followed", "Documentation complete", "Regulations met"],
                    "good": ["Most procedures followed", "Good documentation"],
                    "satisfactory": ["Basic compliance met"],
                    "needs_improvement": ["Some procedures missed"],
                    "poor": ["Non-compliant", "Major violations"]
                }
            },
            QualityDimension.CLOSURE: {
                "weight": 0.10,
                "criteria": {
                    "excellent": ["Perfect closure", "Summary provided", "Next steps clear", "Thank you"],
                    "good": ["Good closure", "Main points covered"],
                    "satisfactory": ["Basic closure present"],
                    "needs_improvement": ["Rushed closure"],
                    "poor": ["Abrupt ending", "No closure"]
                }
            }
        }
    
    def _load_compliance_rules(self) -> List[Dict[str, Any]]:
        """Load compliance rules"""
        return [
            {"rule": "greeting_required", "description": "Agent must greet customer"},
            {"rule": "identity_verification", "description": "Must verify customer identity"},
            {"rule": "data_privacy", "description": "No sensitive data exposed"},
            {"rule": "script_adherence", "description": "Follow approved scripts"},
            {"rule": "documentation", "description": "Document all interactions"},
            {"rule": "escalation_protocol", "description": "Follow escalation procedures"}
        ]
    
    async def _initialize(self) -> None:
        """Initialize the quality scoring agent"""
        self.logger.info("Initializing Quality Scoring Agent")
        
        # Load ML models for scoring if available
        await self._load_scoring_models()
    
    async def _load_scoring_models(self) -> None:
        """Load ML models for advanced scoring"""
        # In production, load pre-trained models for sentiment, satisfaction prediction, etc.
        self.logger.info("Scoring models loaded (mock)")
    
    async def _start(self) -> None:
        """Start the quality scoring agent"""
        self.logger.info("Starting Quality Scoring Agent")
        
        # Start periodic quality reviews
        task = asyncio.create_task(self._periodic_quality_review())
        self._tasks.append(task)
    
    async def _stop(self) -> None:
        """Stop the quality scoring agent"""
        self.logger.info("Stopping Quality Scoring Agent")
    
    async def handle_message(self, message: Message) -> None:
        """Handle incoming messages"""
        if message.type == MessageType.QUALITY_SCORE:
            await self._handle_quality_request(message)
        else:
            self.logger.warning(f"Received unexpected message type: {message.type}")
    
    async def _handle_quality_request(self, message: Message) -> None:
        """Process quality scoring request"""
        try:
            call_id = message.payload.get("call_id")
            summary = message.payload.get("summary", {})
            transcript = message.payload.get("transcript", "")
            metadata = message.payload.get("metadata", {})
            
            # Perform quality assessment
            assessment = await self._assess_call_quality(
                call_id, summary, transcript, metadata
            )
            
            # Store assessment
            self.assessments[call_id] = assessment
            
            # Send assessment results
            await self._send_assessment_results(assessment)
            
            # Check if coaching is needed
            if assessment.overall_score < 70:
                await self._trigger_coaching_alert(assessment)
            
        except Exception as e:
            self.logger.error(f"Error handling quality request: {e}")
            await self._send_error_response(message, str(e))
    
    async def _assess_call_quality(
        self,
        call_id: str,
        summary: Dict[str, Any],
        transcript: str,
        metadata: Dict[str, Any]
    ) -> CallQualityAssessment:
        """Perform comprehensive quality assessment"""
        
        dimension_scores = []
        total_weighted_score = 0
        
        # Evaluate each dimension
        for dimension, rubric in self.scoring_rubric.items():
            score = await self._evaluate_dimension(
                dimension, transcript, summary, rubric
            )
            dimension_scores.append(score)
            total_weighted_score += score.score * rubric["weight"]
        
        # Calculate overall score
        overall_score = int(total_weighted_score)
        overall_level = self._determine_level(overall_score)
        
        # Evaluate compliance
        compliance_status = await self._check_compliance(transcript, metadata)
        
        # Analyze sentiment
        sentiment_score = await self._analyze_sentiment(transcript, summary)
        
        # Calculate other metrics
        professionalism_score = await self._calculate_professionalism(transcript)
        resolution_effectiveness = await self._calculate_resolution_effectiveness(summary)
        customer_satisfaction_predicted = await self._predict_satisfaction(
            overall_score, sentiment_score, resolution_effectiveness
        )
        
        # Generate insights
        strengths = self._identify_strengths(dimension_scores)
        improvements = self._identify_improvements(dimension_scores)
        coaching = self._generate_coaching_recommendations(dimension_scores, overall_score)
        
        return CallQualityAssessment(
            call_id=call_id,
            overall_score=overall_score,
            overall_level=overall_level,
            dimension_scores=dimension_scores,
            compliance_status=compliance_status,
            sentiment_score=sentiment_score,
            professionalism_score=professionalism_score,
            resolution_effectiveness=resolution_effectiveness,
            customer_satisfaction_predicted=customer_satisfaction_predicted,
            strengths=strengths,
            areas_for_improvement=improvements,
            coaching_recommendations=coaching
        )
    
    async def _evaluate_dimension(
        self,
        dimension: QualityDimension,
        transcript: str,
        summary: Dict[str, Any],
        rubric: Dict[str, Any]
    ) -> QualityScore:
        """Evaluate a specific quality dimension"""
        
        # Analyze transcript for dimension-specific indicators
        score = 0
        level = ScoreLevel.POOR
        notes = ""
        
        # Mock evaluation logic (in production, use NLP/ML models)
        if dimension == QualityDimension.GREETING:
            if "thank you for calling" in transcript.lower():
                score = 85
                level = ScoreLevel.GOOD
                notes = "Professional greeting detected"
            elif "hello" in transcript.lower() or "hi" in transcript.lower():
                score = 60
                level = ScoreLevel.SATISFACTORY
                notes = "Basic greeting present"
            else:
                score = 30
                level = ScoreLevel.NEEDS_IMPROVEMENT
                notes = "No clear greeting found"
        
        elif dimension == QualityDimension.SOLUTION_PROVIDED:
            resolution_status = summary.get("resolution_status", "pending")
            if resolution_status == "resolved":
                score = 90
                level = ScoreLevel.EXCELLENT
                notes = "Issue successfully resolved"
            elif resolution_status == "escalated":
                score = 60
                level = ScoreLevel.SATISFACTORY
                notes = "Issue escalated appropriately"
            else:
                score = 40
                level = ScoreLevel.NEEDS_IMPROVEMENT
                notes = "Resolution pending"
        
        else:
            # Default scoring for other dimensions
            score = 70
            level = ScoreLevel.SATISFACTORY
            notes = f"Standard evaluation for {dimension.value}"
        
        return QualityScore(
            dimension=dimension,
            score=score,
            level=level,
            notes=notes
        )
    
    async def _check_compliance(self, transcript: str, metadata: Dict[str, Any]) -> bool:
        """Check compliance with rules"""
        violations = []
        
        for rule in self.compliance_rules:
            if rule["rule"] == "greeting_required":
                if not any(greeting in transcript.lower() for greeting in ["hello", "hi", "thank you for calling"]):
                    violations.append(rule["rule"])
            
            elif rule["rule"] == "identity_verification":
                if "account" not in transcript.lower() and "verify" not in transcript.lower():
                    violations.append(rule["rule"])
        
        return len(violations) == 0
    
    async def _analyze_sentiment(self, transcript: str, summary: Dict[str, Any]) -> float:
        """Analyze overall sentiment"""
        # Mock sentiment analysis (in production, use sentiment analysis model)
        sentiment = summary.get("sentiment", "neutral")
        
        sentiment_scores = {
            "positive": 0.8,
            "neutral": 0.0,
            "negative": -0.8
        }
        
        return sentiment_scores.get(sentiment, 0.0)
    
    async def _calculate_professionalism(self, transcript: str) -> float:
        """Calculate professionalism score"""
        # Mock calculation (in production, use NLP to detect professional language)
        professional_indicators = ["certainly", "please", "thank you", "appreciate", "assist"]
        unprofessional_indicators = ["um", "uh", "like", "whatever", "yeah"]
        
        prof_count = sum(1 for word in professional_indicators if word in transcript.lower())
        unprof_count = sum(1 for word in unprofessional_indicators if word in transcript.lower())
        
        if prof_count + unprof_count == 0:
            return 0.5
        
        return prof_count / (prof_count + unprof_count)
    
    async def _calculate_resolution_effectiveness(self, summary: Dict[str, Any]) -> float:
        """Calculate resolution effectiveness"""
        resolution_status = summary.get("resolution_status", "pending")
        
        effectiveness_scores = {
            "resolved": 1.0,
            "escalated": 0.6,
            "pending": 0.3,
            "unresolved": 0.0
        }
        
        return effectiveness_scores.get(resolution_status, 0.5)
    
    async def _predict_satisfaction(
        self,
        overall_score: int,
        sentiment: float,
        resolution: float
    ) -> float:
        """Predict customer satisfaction"""
        # Weighted combination of factors
        satisfaction = (
            (overall_score / 100) * 0.4 +
            ((sentiment + 1) / 2) * 0.3 +
            resolution * 0.3
        )
        
        return min(max(satisfaction, 0), 1)
    
    def _determine_level(self, score: int) -> ScoreLevel:
        """Determine score level based on numeric score"""
        if score >= self.benchmark_scores["excellent"]:
            return ScoreLevel.EXCELLENT
        elif score >= self.benchmark_scores["good"]:
            return ScoreLevel.GOOD
        elif score >= self.benchmark_scores["satisfactory"]:
            return ScoreLevel.SATISFACTORY
        elif score >= self.benchmark_scores["needs_improvement"]:
            return ScoreLevel.NEEDS_IMPROVEMENT
        else:
            return ScoreLevel.POOR
    
    def _identify_strengths(self, dimension_scores: List[QualityScore]) -> List[str]:
        """Identify call strengths"""
        strengths = []
        
        for score in dimension_scores:
            if score.score >= 80:
                strengths.append(f"Strong {score.dimension.value.replace('_', ' ')}")
        
        return strengths[:3]  # Top 3 strengths
    
    def _identify_improvements(self, dimension_scores: List[QualityScore]) -> List[str]:
        """Identify areas for improvement"""
        improvements = []
        
        for score in dimension_scores:
            if score.score < 60:
                improvements.append(f"Improve {score.dimension.value.replace('_', ' ')}")
        
        return improvements[:3]  # Top 3 improvements
    
    def _generate_coaching_recommendations(
        self,
        dimension_scores: List[QualityScore],
        overall_score: int
    ) -> List[str]:
        """Generate coaching recommendations"""
        recommendations = []
        
        if overall_score < 60:
            recommendations.append("Schedule immediate coaching session")
        
        # Specific recommendations based on low scores
        for score in dimension_scores:
            if score.score < 50:
                if score.dimension == QualityDimension.GREETING:
                    recommendations.append("Practice standard greeting scripts")
                elif score.dimension == QualityDimension.EMPATHY:
                    recommendations.append("Empathy training recommended")
                elif score.dimension == QualityDimension.SOLUTION_PROVIDED:
                    recommendations.append("Product knowledge refresher needed")
        
        return recommendations[:3]
    
    async def _send_assessment_results(self, assessment: CallQualityAssessment) -> None:
        """Send assessment results"""
        message = Message(
            type=MessageType.QUALITY_SCORE,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": assessment.call_id,
                "assessment": assessment.dict(),
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        await self.send_message(message)
        self.logger.info(f"Sent quality assessment for call {assessment.call_id}")
    
    async def _trigger_coaching_alert(self, assessment: CallQualityAssessment) -> None:
        """Trigger coaching alert for low scores"""
        message = Message(
            type=MessageType.ROUTING,
            sender=self.name,
            recipient="RoutingAgent",
            payload={
                "call_id": assessment.call_id,
                "alert_type": "coaching_needed",
                "score": assessment.overall_score,
                "recommendations": assessment.coaching_recommendations
            }
        )
        
        await self.send_message(message)
    
    async def _periodic_quality_review(self) -> None:
        """Perform periodic quality reviews"""
        while self._running:
            try:
                # Review recent assessments
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Generate quality reports
                if len(self.assessments) > 0:
                    await self._generate_quality_report()
                
            except Exception as e:
                self.logger.error(f"Error in periodic quality review: {e}")
    
    async def _generate_quality_report(self) -> None:
        """Generate quality report"""
        # Calculate aggregate metrics
        total_calls = len(self.assessments)
        avg_score = sum(a.overall_score for a in self.assessments.values()) / total_calls
        
        self.logger.info(f"Quality Report: {total_calls} calls, Average Score: {avg_score:.1f}")
    
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