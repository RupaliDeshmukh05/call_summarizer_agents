"""Main application entry point for Call Center AI System"""

import asyncio
import sys
import signal
from typing import Dict, Any, Optional
from pathlib import Path
import uvicorn
import click

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from core import setup_logging, get_logger, AgentConfig
from core.base_agent import BaseAgent
from database import initialize_database, get_database
from communication import MessageBus, MessageBrokerType, EventSystem
from agents.intake_agent import IntakeAgent
from agents.transcription_agent import TranscriptionAgent
from agents.summarization_agent import SummarizationAgent
from agents.quality_score_agent import QualityScoringAgent
from agents.routing_agent import RoutingAgent


class CallCenterSystem:
    """Main system orchestrator"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.agents: Dict[str, BaseAgent] = {}
        self.message_bus: Optional[MessageBus] = None
        self.event_system: Optional[EventSystem] = None
        self.is_running = False
        
        # Setup logging
        setup_logging(
            log_level=settings.log_level,
            log_file=settings.log_file,
            json_format=settings.is_production
        )
    
    async def initialize(self) -> None:
        """Initialize the entire system"""
        try:
            self.logger.info("Initializing Call Center AI System...")
            
            # Initialize database
            await self._initialize_database()
            
            # Initialize message bus
            await self._initialize_message_bus()
            
            # Initialize event system
            await self._initialize_event_system()
            
            # Initialize and register agents
            await self._initialize_agents()
            
            # Setup signal handlers
            self._setup_signal_handlers()
            
            self.logger.info("System initialization complete")
            
        except Exception as e:
            self.logger.error(f"System initialization failed: {e}")
            await self.shutdown()
            raise
    
    async def _initialize_database(self) -> None:
        """Initialize database connections"""
        self.logger.info("Initializing database...")
        await initialize_database(
            database_url=settings.database_url,
            redis_url=settings.redis_url
        )
        
        # Test database connection
        db = get_database()
        async with db.get_session() as session:
            self.logger.info("Database connection established")
    
    async def _initialize_message_bus(self) -> None:
        """Initialize message bus for inter-agent communication"""
        self.logger.info("Initializing message bus...")
        
        # Determine broker type based on configuration
        if settings.rabbitmq_url:
            broker_type = MessageBrokerType.RABBITMQ
            connection_config = {"url": settings.rabbitmq_url}
        elif settings.redis_url:
            broker_type = MessageBrokerType.REDIS
            connection_config = {"url": settings.redis_url}
        else:
            broker_type = MessageBrokerType.MEMORY
            connection_config = {}
        
        self.message_bus = MessageBus(broker_type, connection_config)
        await self.message_bus.initialize()
        
        self.logger.info(f"Message bus initialized with {broker_type.value} broker")
    
    async def _initialize_event_system(self) -> None:
        """Initialize event system"""
        self.logger.info("Initializing event system...")
        self.event_system = EventSystem()
        await self.event_system.start()
    
    async def _initialize_agents(self) -> None:
        """Initialize all agents"""
        self.logger.info("Initializing agents...")
        
        # Agent configurations
        agent_configs = {
            "IntakeAgent": AgentConfig(
                name="IntakeAgent",
                type="intake",
                custom_config={
                    "company_name": settings.app_name,
                    "enable_telephony": bool(settings.twilio_account_sid),
                    "greeting_template": "Thank you for calling {company_name}. My name is {agent_name}. How may I assist you today?"
                }
            ),
            "TranscriptionAgent": AgentConfig(
                name="TranscriptionAgent", 
                type="transcription",
                custom_config={
                    "provider": "deepgram" if settings.deepgram_api_key else "whisper",
                    "deepgram_api_key": settings.deepgram_api_key,
                    "language": settings.transcription_language
                }
            ),
            "SummarizationAgent": AgentConfig(
                name="SummarizationAgent",
                type="summarization",
                custom_config={
                    "openai_api_key": settings.openai_api_key,
                    "model": settings.openai_model,
                    "max_summary_length": settings.summary_max_length
                }
            ),
            "QualityScoringAgent": AgentConfig(
                name="QualityScoringAgent",
                type="quality_scoring"
            ),
            "RoutingAgent": AgentConfig(
                name="RoutingAgent",
                type="routing",
                custom_config={
                    "max_queue_time": 300,
                    "auto_resolve_threshold": 0.8,
                    "escalation_threshold": 0.3
                }
            )
        }
        
        # Initialize each agent
        for agent_name, config in agent_configs.items():
            try:
                # Create agent instance
                if agent_name == "IntakeAgent":
                    agent = IntakeAgent(config)
                elif agent_name == "TranscriptionAgent":
                    agent = TranscriptionAgent(config)
                elif agent_name == "SummarizationAgent":
                    agent = SummarizationAgent(config)
                elif agent_name == "QualityScoringAgent":
                    agent = QualityScoringAgent(config)
                elif agent_name == "RoutingAgent":
                    agent = RoutingAgent(config)
                else:
                    continue
                
                # Initialize and start agent
                await agent.initialize()
                await agent.start()
                
                # Store agent reference
                self.agents[agent_name] = agent
                
                # Subscribe agent to message bus
                await self._subscribe_agent_to_bus(agent)
                
                self.logger.info(f"Agent {agent_name} initialized and started")
                
            except Exception as e:
                self.logger.error(f"Failed to initialize agent {agent_name}: {e}")
                raise
    
    async def _subscribe_agent_to_bus(self, agent: BaseAgent) -> None:
        """Subscribe agent to appropriate message bus topics"""
        # Subscribe to agent-specific topics
        agent_topic = f"agent_{agent.name.lower()}"
        await self.message_bus.subscribe(
            agent_topic,
            agent.receive_message
        )
        
        # Subscribe to broadcast topics
        await self.message_bus.subscribe(
            "broadcast",
            agent.receive_message
        )
    
    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def start(self) -> None:
        """Start the system"""
        if self.is_running:
            return
        
        self.logger.info("Starting Call Center AI System...")
        self.is_running = True
        
        # Start all agents
        for agent_name, agent in self.agents.items():
            if agent.state.value != "ready":
                await agent.start()
            self.logger.info(f"Agent {agent_name} is running")
        
        self.logger.info("Call Center AI System is running")
        
        # Keep the system running
        try:
            while self.is_running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        finally:
            await self.shutdown()
    
    async def shutdown(self) -> None:
        """Shutdown the system gracefully"""
        if not self.is_running:
            return
        
        self.logger.info("Shutting down Call Center AI System...")
        self.is_running = False
        
        # Stop all agents
        for agent_name, agent in self.agents.items():
            try:
                await agent.stop()
                self.logger.info(f"Agent {agent_name} stopped")
            except Exception as e:
                self.logger.error(f"Error stopping agent {agent_name}: {e}")
        
        # Shutdown message bus
        if self.message_bus:
            await self.message_bus.shutdown()
        
        # Shutdown event system
        if self.event_system:
            await self.event_system.stop()
        
        # Shutdown database
        try:
            db = get_database()
            await db.shutdown()
        except Exception as e:
            self.logger.error(f"Error shutting down database: {e}")
        
        self.logger.info("System shutdown complete")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            "is_running": self.is_running,
            "agents": {
                name: agent.get_status() 
                for name, agent in self.agents.items()
            },
            "message_bus": self.message_bus.get_metrics() if self.message_bus else None,
            "event_system": self.event_system.get_metrics() if self.event_system else None
        }


# CLI Commands
@click.group()
def cli():
    """Call Center AI System CLI"""
    pass


@cli.command()
@click.option('--host', default='0.0.0.0', help='Host to bind to')
@click.option('--port', default=8000, help='Port to bind to')
@click.option('--reload', is_flag=True, help='Enable auto-reload')
def api(host, port, reload):
    """Start the API server"""
    from api.main import app
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        reload=reload and settings.debug,
        log_level=settings.log_level.lower()
    )


@cli.command()
def dashboard():
    """Start the Streamlit dashboard"""
    import streamlit.web.cli as stcli
    import sys
    
    sys.argv = ["streamlit", "run", "frontend/dashboard.py"]
    stcli.main()


@cli.command()
def system():
    """Start the complete system (agents only)"""
    async def run_system():
        system = CallCenterSystem()
        await system.initialize()
        await system.start()
    
    asyncio.run(run_system())


@cli.command()
def status():
    """Get system status"""
    # This would connect to running system and get status
    click.echo("System status checking not implemented yet")


@cli.command()
@click.option('--agent', help='Specific agent to start')
def agent(agent_name):
    """Start a specific agent"""
    if not agent_name:
        click.echo("Please specify agent name with --agent")
        return
    
    async def run_agent():
        system = CallCenterSystem()
        await system.initialize()
        
        if agent_name in system.agents:
            agent_instance = system.agents[agent_name]
            click.echo(f"Starting agent: {agent_name}")
            
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                await agent_instance.stop()
        else:
            click.echo(f"Agent '{agent_name}' not found")
    
    asyncio.run(run_agent())


@cli.command()
def test():
    """Run system tests"""
    import subprocess
    
    result = subprocess.run([
        sys.executable, "-m", "pytest", 
        "tests/", "-v", "--cov=."
    ])
    sys.exit(result.returncode)


if __name__ == "__main__":
    cli()