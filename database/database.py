"""Database connection and session management"""

import asyncio
from typing import AsyncGenerator, Dict, Any, Optional, List
from contextlib import asynccontextmanager
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload
from sqlalchemy import select, update, delete, func
from sqlalchemy.exc import SQLAlchemyError
import redis.asyncio as redis
from datetime import datetime, timedelta

from core import get_logger
from core.exceptions import DatabaseException
from .models import Base, Call, Customer, Agent, Transcript, Summary, QualityAssessment, RoutingDecision


class Database:
    """Database manager for the Call Center System"""
    
    def __init__(self, database_url: str, redis_url: Optional[str] = None):
        self.database_url = database_url
        self.redis_url = redis_url
        self.engine = None
        self.session_factory = None
        self.redis_client = None
        self.logger = get_logger(__name__)
        self.is_connected = False
    
    async def initialize(self) -> None:
        """Initialize database connections"""
        try:
            # Database connection
            if "sqlite" in self.database_url:
                # SQLite doesn't support pool settings
                self.engine = create_async_engine(
                    self.database_url,
                    echo=False
                )
            else:
                # PostgreSQL connection with pool settings
                self.engine = create_async_engine(
                    self.database_url,
                    echo=False,
                    pool_size=10,
                    max_overflow=20,
                    pool_pre_ping=True,
                    pool_recycle=3600
                )
            
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Create tables
            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            
            # Redis connection for caching
            if self.redis_url:
                self.redis_client = redis.from_url(self.redis_url)
                await self.redis_client.ping()
                self.logger.info("Connected to Redis")
            
            self.is_connected = True
            self.logger.info("Database initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise DatabaseException(f"Database initialization failed: {e}")
    
    async def shutdown(self) -> None:
        """Shutdown database connections"""
        if self.engine:
            await self.engine.dispose()
        
        if self.redis_client:
            await self.redis_client.close()
        
        self.is_connected = False
        self.logger.info("Database connections closed")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Get database session context manager"""
        if not self.is_connected:
            raise DatabaseException("Database not connected")
        
        async with self.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception as e:
                await session.rollback()
                self.logger.error(f"Database session error: {e}")
                raise DatabaseException(f"Database operation failed: {e}")
            finally:
                await session.close()
    
    # Customer operations
    async def create_customer(self, customer_data: Dict[str, Any]) -> str:
        """Create a new customer"""
        async with self.get_session() as session:
            customer = Customer(**customer_data)
            session.add(customer)
            await session.flush()
            return customer.id
    
    async def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """Get customer by ID"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Customer).where(Customer.id == customer_id)
            )
            customer = result.scalar_one_or_none()
            return customer.__dict__ if customer else None
    
    async def get_customer_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """Get customer by phone number"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Customer).where(Customer.phone == phone)
            )
            customer = result.scalar_one_or_none()
            return customer.__dict__ if customer else None
    
    # Agent operations
    async def create_agent(self, agent_data: Dict[str, Any]) -> str:
        """Create a new agent"""
        async with self.get_session() as session:
            agent = Agent(**agent_data)
            session.add(agent)
            await session.flush()
            return agent.id
    
    async def get_active_agents(self) -> List[Dict[str, Any]]:
        """Get all active agents"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Agent).where(Agent.is_active == True)
            )
            agents = result.scalars().all()
            return [agent.__dict__ for agent in agents]
    
    async def update_agent_load(self, agent_id: str, current_load: int) -> None:
        """Update agent's current load"""
        async with self.get_session() as session:
            await session.execute(
                update(Agent)
                .where(Agent.id == agent_id)
                .values(
                    performance_metrics=func.jsonb_set(
                        Agent.performance_metrics,
                        '{current_load}',
                        str(current_load)
                    ),
                    updated_at=datetime.utcnow()
                )
            )
    
    # Call operations
    async def create_call(self, call_data: Dict[str, Any]) -> str:
        """Create a new call"""
        async with self.get_session() as session:
            call = Call(**call_data)
            session.add(call)
            await session.flush()
            return call.id
    
    async def get_call(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Get call with all related data"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Call)
                .options(
                    selectinload(Call.customer),
                    selectinload(Call.agent),
                    selectinload(Call.transcripts),
                    selectinload(Call.summaries),
                    selectinload(Call.quality_assessments)
                )
                .where(Call.id == call_id)
            )
            call = result.scalar_one_or_none()
            return call.__dict__ if call else None
    
    async def update_call_status(self, call_id: str, status: str, ended_at: Optional[datetime] = None) -> None:
        """Update call status"""
        update_data = {"status": status, "updated_at": datetime.utcnow()}
        if ended_at:
            update_data["ended_at"] = ended_at
        
        async with self.get_session() as session:
            await session.execute(
                update(Call)
                .where(Call.id == call_id)
                .values(**update_data)
            )
    
    async def get_active_calls(self) -> List[Dict[str, Any]]:
        """Get all active calls"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Call)
                .options(selectinload(Call.customer), selectinload(Call.agent))
                .where(Call.status == "active")
                .order_by(Call.started_at.desc())
            )
            calls = result.scalars().all()
            return [call.__dict__ for call in calls]
    
    # Transcript operations
    async def create_transcript(self, transcript_data: Dict[str, Any]) -> str:
        """Create call transcript"""
        async with self.get_session() as session:
            transcript = Transcript(**transcript_data)
            session.add(transcript)
            await session.flush()
            return transcript.id
    
    async def get_transcript(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Get transcript for a call"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Transcript).where(Transcript.call_id == call_id)
            )
            transcript = result.scalar_one_or_none()
            return transcript.__dict__ if transcript else None
    
    # Summary operations
    async def create_summary(self, summary_data: Dict[str, Any]) -> str:
        """Create call summary"""
        async with self.get_session() as session:
            summary = Summary(**summary_data)
            session.add(summary)
            await session.flush()
            return summary.id
    
    async def get_summaries(self, call_id: str) -> List[Dict[str, Any]]:
        """Get all summaries for a call"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Summary)
                .where(Summary.call_id == call_id)
                .order_by(Summary.created_at.desc())
            )
            summaries = result.scalars().all()
            return [summary.__dict__ for summary in summaries]
    
    async def get_final_summary(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Get final summary for a call"""
        async with self.get_session() as session:
            result = await session.execute(
                select(Summary)
                .where(Summary.call_id == call_id, Summary.summary_type == "final")
                .order_by(Summary.created_at.desc())
                .limit(1)
            )
            summary = result.scalar_one_or_none()
            return summary.__dict__ if summary else None
    
    # Quality assessment operations
    async def create_quality_assessment(self, assessment_data: Dict[str, Any]) -> str:
        """Create quality assessment"""
        async with self.get_session() as session:
            assessment = QualityAssessment(**assessment_data)
            session.add(assessment)
            await session.flush()
            return assessment.id
    
    async def get_quality_assessment(self, call_id: str) -> Optional[Dict[str, Any]]:
        """Get quality assessment for a call"""
        async with self.get_session() as session:
            result = await session.execute(
                select(QualityAssessment).where(QualityAssessment.call_id == call_id)
            )
            assessment = result.scalar_one_or_none()
            return assessment.__dict__ if assessment else None
    
    # Routing decision operations
    async def create_routing_decision(self, routing_data: Dict[str, Any]) -> str:
        """Create routing decision"""
        async with self.get_session() as session:
            routing = RoutingDecision(**routing_data)
            session.add(routing)
            await session.flush()
            return routing.id
    
    async def get_routing_decisions(self, call_id: str) -> List[Dict[str, Any]]:
        """Get routing decisions for a call"""
        async with self.get_session() as session:
            result = await session.execute(
                select(RoutingDecision)
                .where(RoutingDecision.call_id == call_id)
                .order_by(RoutingDecision.decision_made_at.desc())
            )
            decisions = result.scalars().all()
            return [decision.__dict__ for decision in decisions]
    
    # Analytics and reporting
    async def get_call_statistics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Get call statistics for a date range"""
        async with self.get_session() as session:
            # Total calls
            total_calls_result = await session.execute(
                select(func.count(Call.id))
                .where(Call.started_at.between(start_date, end_date))
            )
            total_calls = total_calls_result.scalar()
            
            # Completed calls
            completed_calls_result = await session.execute(
                select(func.count(Call.id))
                .where(
                    Call.started_at.between(start_date, end_date),
                    Call.status == "completed"
                )
            )
            completed_calls = completed_calls_result.scalar()
            
            # Average duration
            avg_duration_result = await session.execute(
                select(func.avg(Call.duration_seconds))
                .where(
                    Call.started_at.between(start_date, end_date),
                    Call.status == "completed"
                )
            )
            avg_duration = avg_duration_result.scalar() or 0
            
            # Average quality score
            avg_quality_result = await session.execute(
                select(func.avg(QualityAssessment.overall_score))
                .join(Call)
                .where(Call.started_at.between(start_date, end_date))
            )
            avg_quality = avg_quality_result.scalar() or 0
            
            return {
                "total_calls": total_calls,
                "completed_calls": completed_calls,
                "completion_rate": completed_calls / total_calls if total_calls > 0 else 0,
                "average_duration_seconds": float(avg_duration),
                "average_quality_score": float(avg_quality)
            }
    
    async def get_agent_performance(self, agent_id: str, days: int = 30) -> Dict[str, Any]:
        """Get agent performance metrics"""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        async with self.get_session() as session:
            # Agent calls
            calls_result = await session.execute(
                select(func.count(Call.id), func.avg(Call.duration_seconds))
                .where(
                    Call.agent_id == agent_id,
                    Call.started_at >= start_date
                )
            )
            call_count, avg_duration = calls_result.first()
            
            # Average quality score
            quality_result = await session.execute(
                select(func.avg(QualityAssessment.overall_score))
                .join(Call)
                .where(
                    Call.agent_id == agent_id,
                    Call.started_at >= start_date
                )
            )
            avg_quality = quality_result.scalar() or 0
            
            return {
                "agent_id": agent_id,
                "call_count": call_count or 0,
                "average_duration": float(avg_duration) if avg_duration else 0,
                "average_quality_score": float(avg_quality),
                "period_days": days
            }
    
    # Caching operations
    async def cache_set(self, key: str, value: str, expire: int = 3600) -> None:
        """Set cache value"""
        if self.redis_client:
            await self.redis_client.setex(key, expire, value)
    
    async def cache_get(self, key: str) -> Optional[str]:
        """Get cache value"""
        if self.redis_client:
            return await self.redis_client.get(key)
        return None
    
    async def cache_delete(self, key: str) -> None:
        """Delete cache value"""
        if self.redis_client:
            await self.redis_client.delete(key)


# Global database instance
_database: Optional[Database] = None


async def initialize_database(database_url: str, redis_url: Optional[str] = None) -> None:
    """Initialize global database instance"""
    global _database
    _database = Database(database_url, redis_url)
    await _database.initialize()


def get_database() -> Database:
    """Get global database instance"""
    if _database is None:
        raise DatabaseException("Database not initialized")
    return _database