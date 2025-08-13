"""Database models for Call Center System"""

from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text, JSON,
    ForeignKey, Index, UniqueConstraint
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
from typing import Dict, Any, Optional

Base = declarative_base()


class Customer(Base):
    """Customer model"""
    __tablename__ = "customers"
    
    id = Column(String, primary_key=True)
    name = Column(String(255))
    email = Column(String(255))
    phone = Column(String(50))
    account_number = Column(String(100), unique=True)
    language_preference = Column(String(10), default="en")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    calls = relationship("Call", back_populates="customer")
    
    # Indexes
    __table_args__ = (
        Index("idx_customer_phone", phone),
        Index("idx_customer_account", account_number),
        Index("idx_customer_email", email),
    )


class Agent(Base):
    """Agent model (human or AI agents)"""
    __tablename__ = "agents"
    
    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    type = Column(String(50))  # human, ai, supervisor
    skill_level = Column(String(50))  # junior, intermediate, senior, specialist, supervisor
    specializations = Column(JSON)  # List of specialization areas
    languages = Column(JSON)  # List of supported languages
    max_capacity = Column(Integer, default=5)
    is_active = Column(Boolean, default=True)
    performance_metrics = Column(JSON)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    calls = relationship("Call", back_populates="agent")
    routing_decisions = relationship("RoutingDecision", back_populates="assigned_agent")
    
    # Indexes
    __table_args__ = (
        Index("idx_agent_type", type),
        Index("idx_agent_skill", skill_level),
        Index("idx_agent_active", is_active),
    )


class Call(Base):
    """Call model"""
    __tablename__ = "calls"
    
    id = Column(String, primary_key=True)
    customer_id = Column(String, ForeignKey("customers.id"))
    agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    
    # Call details
    phone_number = Column(String(50))
    direction = Column(String(20))  # inbound, outbound
    status = Column(String(50))  # active, completed, abandoned, transferred
    priority = Column(String(20))  # low, normal, high, urgent
    category = Column(String(100))
    
    # Timestamps
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime)
    duration_seconds = Column(Integer)
    wait_time_seconds = Column(Integer)
    
    # Metadata
    call_metadata = Column(JSON)
    notes = Column(Text)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("Customer", back_populates="calls")
    agent = relationship("Agent", back_populates="calls")
    transcripts = relationship("Transcript", back_populates="call")
    summaries = relationship("Summary", back_populates="call")
    quality_assessments = relationship("QualityAssessment", back_populates="call")
    routing_decisions = relationship("RoutingDecision", back_populates="call")
    
    # Indexes
    __table_args__ = (
        Index("idx_call_customer", customer_id),
        Index("idx_call_agent", agent_id),
        Index("idx_call_status", status),
        Index("idx_call_priority", priority),
        Index("idx_call_started", started_at),
        Index("idx_call_category", category),
    )


class Transcript(Base):
    """Call transcript model"""
    __tablename__ = "transcripts"
    
    id = Column(String, primary_key=True)
    call_id = Column(String, ForeignKey("calls.id"), nullable=False)
    
    # Transcript content
    full_transcript = Column(Text)
    segments = Column(JSON)  # List of transcript segments with speaker info
    speakers = Column(JSON)  # List of identified speakers
    
    # Processing info
    provider = Column(String(50))  # deepgram, whisper, google
    language = Column(String(10))
    confidence_score = Column(Float)
    processing_time_ms = Column(Integer)
    
    # Timestamps
    transcription_started_at = Column(DateTime)
    transcription_completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", back_populates="transcripts")
    
    # Indexes
    __table_args__ = (
        Index("idx_transcript_call", call_id),
        Index("idx_transcript_provider", provider),
        Index("idx_transcript_completed", transcription_completed_at),
    )


class Summary(Base):
    """Call summary model"""
    __tablename__ = "summaries"
    
    id = Column(String, primary_key=True)
    call_id = Column(String, ForeignKey("calls.id"), nullable=False)
    
    # Summary content
    summary_type = Column(String(50))  # real_time, periodic, final
    summary_text = Column(Text)
    key_points = Column(JSON)  # List of key points
    action_items = Column(JSON)  # List of action items
    customer_issues = Column(JSON)  # List of issues
    topics = Column(JSON)  # List of topics discussed
    
    # Analysis results
    sentiment = Column(String(20))  # positive, neutral, negative
    resolution_status = Column(String(50))  # resolved, pending, escalated
    confidence_score = Column(Float)
    
    # Processing info
    model_used = Column(String(100))  # GPT model version
    processing_time_ms = Column(Integer)
    token_usage = Column(JSON)  # Token usage statistics
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", back_populates="summaries")
    
    # Indexes
    __table_args__ = (
        Index("idx_summary_call", call_id),
        Index("idx_summary_type", summary_type),
        Index("idx_summary_sentiment", sentiment),
        Index("idx_summary_resolution", resolution_status),
        Index("idx_summary_created", created_at),
    )


class QualityAssessment(Base):
    """Quality assessment model"""
    __tablename__ = "quality_assessments"
    
    id = Column(String, primary_key=True)
    call_id = Column(String, ForeignKey("calls.id"), nullable=False)
    
    # Overall scoring
    overall_score = Column(Integer)  # 0-100
    overall_level = Column(String(50))  # excellent, good, satisfactory, etc.
    
    # Dimension scores
    dimension_scores = Column(JSON)  # Detailed scoring by dimension
    
    # Analysis results
    compliance_status = Column(Boolean)
    sentiment_score = Column(Float)  # -1 to 1
    professionalism_score = Column(Float)  # 0 to 1
    resolution_effectiveness = Column(Float)  # 0 to 1
    customer_satisfaction_predicted = Column(Float)  # 0 to 1
    
    # Insights
    strengths = Column(JSON)  # List of identified strengths
    areas_for_improvement = Column(JSON)  # List of improvement areas
    coaching_recommendations = Column(JSON)  # List of coaching suggestions
    
    # Processing info
    assessor = Column(String(100))  # AI Quality System, human assessor, etc.
    assessment_model_version = Column(String(50))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    call = relationship("Call", back_populates="quality_assessments")
    
    # Indexes
    __table_args__ = (
        Index("idx_quality_call", call_id),
        Index("idx_quality_score", overall_score),
        Index("idx_quality_level", overall_level),
        Index("idx_quality_compliance", compliance_status),
        Index("idx_quality_created", created_at),
    )


class RoutingDecision(Base):
    """Call routing decision model"""
    __tablename__ = "routing_decisions"
    
    id = Column(String, primary_key=True)
    call_id = Column(String, ForeignKey("calls.id"), nullable=False)
    assigned_agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    
    # Routing details
    decision_type = Column(String(50))  # auto_resolve, agent_transfer, escalate, etc.
    routing_rule_id = Column(String(100))
    decision_confidence = Column(Float)
    
    # Factors influencing decision
    routing_factors = Column(JSON)  # Priority, category, complexity, etc.
    queue_time_seconds = Column(Integer)
    
    # Results
    execution_status = Column(String(50))  # pending, completed, failed
    execution_notes = Column(Text)
    
    # Timestamps
    decision_made_at = Column(DateTime, default=datetime.utcnow)
    executed_at = Column(DateTime)
    
    # Relationships
    call = relationship("Call", back_populates="routing_decisions")
    assigned_agent = relationship("Agent", back_populates="routing_decisions")
    
    # Indexes
    __table_args__ = (
        Index("idx_routing_call", call_id),
        Index("idx_routing_agent", assigned_agent_id),
        Index("idx_routing_type", decision_type),
        Index("idx_routing_status", execution_status),
        Index("idx_routing_decided", decision_made_at),
    )


class SystemMetric(Base):
    """System metrics model"""
    __tablename__ = "system_metrics"
    
    id = Column(String, primary_key=True)
    metric_name = Column(String(100), nullable=False)
    metric_type = Column(String(50))  # counter, gauge, histogram
    value = Column(Float)
    tags = Column(JSON)  # Additional metric tags
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Indexes
    __table_args__ = (
        Index("idx_metric_name", metric_name),
        Index("idx_metric_timestamp", timestamp),
        Index("idx_metric_name_timestamp", metric_name, timestamp),
    )


class CallEvent(Base):
    """Call event log model"""
    __tablename__ = "call_events"
    
    id = Column(String, primary_key=True)
    call_id = Column(String, ForeignKey("calls.id"), nullable=False)
    
    event_type = Column(String(100))  # call_started, transcription_completed, etc.
    event_source = Column(String(100))  # Agent name or system component
    event_data = Column(JSON)
    correlation_id = Column(String(100))
    
    timestamp = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    call = relationship("Call")
    
    # Indexes
    __table_args__ = (
        Index("idx_event_call", call_id),
        Index("idx_event_type", event_type),
        Index("idx_event_timestamp", timestamp),
        Index("idx_event_correlation", correlation_id),
    )