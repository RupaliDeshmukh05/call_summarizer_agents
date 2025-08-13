"""FastAPI application for Call Center System"""

import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, Any

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from config.settings import settings
from core import setup_logging, get_logger
from database import initialize_database, get_database
from communication import MessageBus, MessageBrokerType


# Setup logging
setup_logging(
    log_level=settings.log_level,
    log_file=settings.log_file,
    json_format=settings.is_production
)

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting API application...")
    
    try:
        # Initialize database
        await initialize_database(
            database_url=settings.database_url,
            redis_url=settings.redis_url if settings.redis_url else None
        )
        
        # Initialize message bus
        broker_type = MessageBrokerType.MEMORY  # Use memory broker for API-only mode
        message_bus = MessageBus(broker_type, {})
        await message_bus.initialize()
        
        app.state.message_bus = message_bus
        app.state.database = get_database()
        
        logger.info("API application startup complete")
        
    except Exception as e:
        logger.error(f"API startup failed: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down API application...")
    
    try:
        if hasattr(app.state, 'message_bus'):
            await app.state.message_bus.shutdown()
        
        if hasattr(app.state, 'database'):
            await app.state.database.shutdown()
            
    except Exception as e:
        logger.error(f"API shutdown error: {e}")
    
    logger.info("API application shutdown complete")


def create_app() -> FastAPI:
    """Create FastAPI application"""
    
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="AI-powered Call Center Multi-Agent System API",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
        lifespan=lifespan
    )
    
    # Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:3000", "http://localhost:8501"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Exception handlers
    @app.exception_handler(404)
    async def not_found_handler(request, exc):
        return JSONResponse(
            status_code=404,
            content={"error": "Not found", "detail": str(exc)}
        )
    
    @app.exception_handler(500)
    async def internal_error_handler(request, exc):
        logger.error(f"Internal server error: {exc}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error"}
        )
    
    # Routes
    @app.get("/")
    async def root():
        """Root endpoint"""
        return {
            "message": "AI Call Center System API",
            "version": settings.app_version,
            "status": "running"
        }
    
    @app.get("/health")
    async def health_check():
        """Health check endpoint"""
        try:
            # Check database connection
            db = get_database()
            if db.is_connected:
                db_status = "connected"
            else:
                db_status = "disconnected"
            
            return {
                "status": "healthy",
                "timestamp": "2024-01-01T00:00:00Z",
                "version": settings.app_version,
                "database": db_status,
                "environment": settings.environment.value
            }
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": str(e)
                }
            )
    
    @app.get("/api/v1/status")
    async def system_status():
        """Get system status"""
        return {
            "system": "AI Call Center",
            "status": "running",
            "agents": {
                "intake": "ready",
                "transcription": "ready", 
                "summarization": "ready",
                "quality": "ready",
                "routing": "ready"
            },
            "services": {
                "database": "connected",
                "message_bus": "active",
                "voice_integration": "configured"
            }
        }
    
    # Mock API endpoints for development
    @app.post("/api/v1/calls")
    async def create_call(call_data: Dict[str, Any]):
        """Create a new call"""
        import uuid
        from datetime import datetime
        
        call_id = f"CALL-{str(uuid.uuid4())[:8].upper()}"
        
        # Mock call creation
        mock_call = {
            "call_id": call_id,
            "customer_phone": call_data.get("customer_phone"),
            "status": "initiated",
            "priority": call_data.get("priority", "normal"),
            "created_at": datetime.utcnow().isoformat(),
            "metadata": call_data.get("metadata", {})
        }
        
        logger.info(f"Created mock call {call_id}")
        
        return {
            "success": True,
            "call": mock_call,
            "message": f"Call {call_id} created successfully"
        }
    
    @app.get("/api/v1/calls/{call_id}")
    async def get_call(call_id: str):
        """Get call details"""
        # Mock call data
        mock_call = {
            "call_id": call_id,
            "customer_name": "John Doe",
            "customer_phone": "+1-555-0123",
            "agent": "AI Agent 1",
            "status": "active",
            "priority": "normal",
            "duration": "00:03:45",
            "summary": "Customer calling regarding technical support issue with mobile app",
            "key_points": [
                "App crashes on startup",
                "Customer tried basic restart",
                "Account verification successful"
            ],
            "quality_score": 87,
            "transcript": "Agent: Thank you for calling. How can I help you today?\nCustomer: Hi, I'm having trouble with your mobile app...",
            "created_at": "2024-01-01T10:00:00Z"
        }
        
        return {
            "success": True,
            "call": mock_call
        }
    
    @app.get("/api/v1/calls")
    async def list_calls(status: str = None, limit: int = 10, offset: int = 0):
        """List calls"""
        # Mock call list
        mock_calls = [
            {
                "call_id": f"CALL-{str(i).zfill(3)}",
                "customer_name": f"Customer {i}",
                "status": "completed" if i % 2 == 0 else "active",
                "priority": "high" if i % 3 == 0 else "normal",
                "created_at": "2024-01-01T10:00:00Z",
                "duration": f"00:0{i}:30" if i % 2 == 0 else None
            }
            for i in range(1, 21)
        ]
        
        # Filter by status if provided
        if status:
            mock_calls = [call for call in mock_calls if call["status"] == status]
        
        # Apply pagination
        paginated_calls = mock_calls[offset:offset + limit]
        
        return {
            "success": True,
            "calls": paginated_calls,
            "total": len(mock_calls),
            "limit": limit,
            "offset": offset
        }
    
    @app.get("/api/v1/agents")
    async def list_agents():
        """List agents"""
        mock_agents = [
            {
                "agent_id": "AGT001",
                "name": "John Smith",
                "type": "human",
                "status": "available",
                "specialization": "technical_support",
                "current_load": 2,
                "max_capacity": 5,
                "quality_score": 89
            },
            {
                "agent_id": "AGT002", 
                "name": "AI Agent 1",
                "type": "ai",
                "status": "available",
                "specialization": "general",
                "current_load": 1,
                "max_capacity": 10,
                "quality_score": 85
            }
        ]
        
        return {
            "success": True,
            "agents": mock_agents
        }
    
    @app.get("/api/v1/analytics/dashboard")
    async def get_dashboard_data():
        """Get dashboard analytics data"""
        mock_data = {
            "metrics": {
                "active_calls": 12,
                "available_agents": 8,
                "average_quality_score": 87,
                "resolution_rate": "94%"
            },
            "call_volume": [
                {"hour": f"{h:02d}:00", "calls": 10 + h + (h % 6) * 3}
                for h in range(24)
            ],
            "quality_trends": [
                {"day": day, "score": 85 + i + (i % 3) * 2}
                for i, day in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"])
            ],
            "recent_activity": [
                {"time": "2 min ago", "event": "📞 New call from +1-555-0123", "status": "active"},
                {"time": "5 min ago", "event": "✅ Call CALL-001 completed with score 92", "status": "completed"},
                {"time": "8 min ago", "event": "🔄 Call CALL-002 transferred to specialist", "status": "transferred"}
            ]
        }
        
        return {
            "success": True,
            "data": mock_data
        }
    
    logger.info("FastAPI application created")
    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=settings.port,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )