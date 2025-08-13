"""Routing Agent - Intelligent call routing and escalation management"""

import asyncio
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from enum import Enum
from dataclasses import dataclass
import random

from core import BaseAgent, AgentConfig, get_logger
from core.base_agent import Message, MessageType
from core.exceptions import RoutingException


class RoutingDecision(str, Enum):
    """Routing decision types"""
    AUTO_RESOLVE = "auto_resolve"
    AGENT_TRANSFER = "agent_transfer"
    ESCALATE = "escalate"
    CALLBACK = "callback"
    END_CALL = "end_call"


class AgentSkillLevel(str, Enum):
    """Agent skill levels"""
    JUNIOR = "junior"
    INTERMEDIATE = "intermediate"
    SENIOR = "senior"
    SPECIALIST = "specialist"
    SUPERVISOR = "supervisor"


@dataclass
class AgentProfile:
    """Profile of a human or AI agent"""
    agent_id: str
    name: str
    skill_level: AgentSkillLevel
    specializations: List[str]
    current_load: int
    max_capacity: int
    availability: bool
    performance_score: float
    languages: List[str]
    
    @property
    def is_available(self) -> bool:
        return self.availability and self.current_load < self.max_capacity
    
    @property
    def load_percentage(self) -> float:
        return (self.current_load / self.max_capacity) * 100 if self.max_capacity > 0 else 0


@dataclass
class RoutingRule:
    """Routing rule definition"""
    rule_id: str
    name: str
    conditions: Dict[str, Any]
    action: RoutingDecision
    priority: int
    target_skill_level: Optional[AgentSkillLevel] = None
    target_specialization: Optional[str] = None


class RoutingAgent(BaseAgent):
    """Agent responsible for intelligent call routing and workload distribution"""
    
    def __init__(self, config: AgentConfig):
        super().__init__(config)
        self.available_agents: Dict[str, AgentProfile] = {}
        self.routing_rules: List[RoutingRule] = []
        self.active_routes: Dict[str, Dict[str, Any]] = {}
        self.queue: List[Dict[str, Any]] = []
        self.routing_history: List[Dict[str, Any]] = []
        
        # Initialize routing configuration
        self.auto_resolve_threshold = config.custom_config.get("auto_resolve_threshold", 0.8)
        self.escalation_threshold = config.custom_config.get("escalation_threshold", 0.3)
        self.max_queue_time = config.custom_config.get("max_queue_time", 300)  # 5 minutes
    
    async def _initialize(self) -> None:
        """Initialize the routing agent"""
        self.logger.info("Initializing Routing Agent")
        
        # Load routing rules
        self.routing_rules = self._load_routing_rules()
        
        # Initialize agent pool
        self._initialize_agent_pool()
        
        # Load routing algorithms
        self.routing_algorithm = self.config.custom_config.get("algorithm", "skill_based")
    
    def _load_routing_rules(self) -> List[RoutingRule]:
        """Load routing rules"""
        return [
            RoutingRule(
                rule_id="R001",
                name="High Priority Escalation",
                conditions={"priority": "urgent", "sentiment": "negative"},
                action=RoutingDecision.ESCALATE,
                priority=1,
                target_skill_level=AgentSkillLevel.SUPERVISOR
            ),
            RoutingRule(
                rule_id="R002",
                name="Technical Issues",
                conditions={"category": "technical", "complexity": "high"},
                action=RoutingDecision.AGENT_TRANSFER,
                priority=2,
                target_skill_level=AgentSkillLevel.SPECIALIST,
                target_specialization="technical_support"
            ),
            RoutingRule(
                rule_id="R003",
                name="Billing Inquiries",
                conditions={"category": "billing"},
                action=RoutingDecision.AGENT_TRANSFER,
                priority=3,
                target_specialization="billing"
            ),
            RoutingRule(
                rule_id="R004",
                name="Simple FAQ",
                conditions={"complexity": "low", "category": "general"},
                action=RoutingDecision.AUTO_RESOLVE,
                priority=4
            ),
            RoutingRule(
                rule_id="R005",
                name="After Hours",
                conditions={"business_hours": False},
                action=RoutingDecision.CALLBACK,
                priority=5
            )
        ]
    
    def _initialize_agent_pool(self) -> None:
        """Initialize available agents"""
        # Mock agent pool (in production, load from database)
        agents = [
            AgentProfile(
                agent_id="AGT001",
                name="Senior Agent 1",
                skill_level=AgentSkillLevel.SENIOR,
                specializations=["technical_support", "billing"],
                current_load=2,
                max_capacity=5,
                availability=True,
                performance_score=0.92,
                languages=["en", "es"]
            ),
            AgentProfile(
                agent_id="AGT002",
                name="Specialist Agent 1",
                skill_level=AgentSkillLevel.SPECIALIST,
                specializations=["technical_support"],
                current_load=3,
                max_capacity=4,
                availability=True,
                performance_score=0.88,
                languages=["en"]
            ),
            AgentProfile(
                agent_id="AGT003",
                name="Junior Agent 1",
                skill_level=AgentSkillLevel.JUNIOR,
                specializations=["general", "billing"],
                current_load=1,
                max_capacity=6,
                availability=True,
                performance_score=0.75,
                languages=["en", "fr"]
            ),
            AgentProfile(
                agent_id="SUP001",
                name="Supervisor 1",
                skill_level=AgentSkillLevel.SUPERVISOR,
                specializations=["all"],
                current_load=0,
                max_capacity=3,
                availability=True,
                performance_score=0.95,
                languages=["en", "es", "fr"]
            )
        ]
        
        for agent in agents:
            self.available_agents[agent.agent_id] = agent
    
    async def _start(self) -> None:
        """Start the routing agent"""
        self.logger.info("Starting Routing Agent")
        
        # Start queue monitoring
        task = asyncio.create_task(self._monitor_queue())
        self._tasks.append(task)
        
        # Start load balancing
        task = asyncio.create_task(self._load_balancer())
        self._tasks.append(task)
    
    async def _stop(self) -> None:
        """Stop the routing agent"""
        self.logger.info("Stopping Routing Agent")
        
        # Process remaining queue items
        await self._process_queue()
    
    async def handle_message(self, message: Message) -> None:
        """Handle incoming messages"""
        if message.type == MessageType.ROUTING:
            await self._handle_routing_request(message)
        else:
            self.logger.warning(f"Received unexpected message type: {message.type}")
    
    async def _handle_routing_request(self, message: Message) -> None:
        """Process routing request"""
        try:
            call_id = message.payload.get("call_id")
            call_metadata = message.payload.get("metadata", {})
            summary = message.payload.get("summary", {})
            quality_score = message.payload.get("quality_score")
            
            # Make routing decision
            decision, target = await self._make_routing_decision(
                call_id, call_metadata, summary, quality_score
            )
            
            # Execute routing decision
            await self._execute_routing(call_id, decision, target, message.payload)
            
            # Update routing history
            self._record_routing_decision(call_id, decision, target)
            
        except Exception as e:
            self.logger.error(f"Error handling routing request: {e}")
            await self._send_error_response(message, str(e))
    
    async def _make_routing_decision(
        self,
        call_id: str,
        metadata: Dict[str, Any],
        summary: Dict[str, Any],
        quality_score: Optional[float]
    ) -> Tuple[RoutingDecision, Optional[str]]:
        """Make intelligent routing decision"""
        
        # Extract routing factors
        priority = metadata.get("priority", "normal")
        category = self._determine_category(summary)
        complexity = self._assess_complexity(summary)
        sentiment = summary.get("sentiment", "neutral")
        resolution_confidence = summary.get("resolution_confidence", 0.5)
        
        # Check routing rules
        for rule in sorted(self.routing_rules, key=lambda r: r.priority):
            if self._check_rule_conditions(rule, {
                "priority": priority,
                "category": category,
                "complexity": complexity,
                "sentiment": sentiment,
                "business_hours": self._is_business_hours()
            }):
                target = None
                if rule.action == RoutingDecision.AGENT_TRANSFER:
                    target = await self._find_best_agent(
                        rule.target_skill_level,
                        rule.target_specialization,
                        metadata.get("language", "en")
                    )
                    if not target:
                        # No agent available, add to queue
                        await self._add_to_queue(call_id, metadata, rule)
                        return RoutingDecision.CALLBACK, None
                
                return rule.action, target
        
        # Default routing based on AI assessment
        if resolution_confidence >= self.auto_resolve_threshold:
            return RoutingDecision.AUTO_RESOLVE, None
        elif quality_score and quality_score < self.escalation_threshold:
            return RoutingDecision.ESCALATE, await self._find_supervisor()
        else:
            # Find best available agent
            target = await self._find_best_agent(
                None, category, metadata.get("language", "en")
            )
            return RoutingDecision.AGENT_TRANSFER, target
    
    def _determine_category(self, summary: Dict[str, Any]) -> str:
        """Determine call category from summary"""
        topics = summary.get("topics", [])
        
        category_keywords = {
            "technical": ["technical", "error", "bug", "crash", "not working"],
            "billing": ["billing", "payment", "invoice", "charge", "refund"],
            "general": ["information", "question", "help", "support"]
        }
        
        for category, keywords in category_keywords.items():
            for topic in topics:
                if any(keyword in topic.lower() for keyword in keywords):
                    return category
        
        return "general"
    
    def _assess_complexity(self, summary: Dict[str, Any]) -> str:
        """Assess call complexity"""
        action_items = summary.get("action_items", [])
        issues = summary.get("customer_issues", [])
        
        if len(action_items) > 3 or len(issues) > 2:
            return "high"
        elif len(action_items) > 1 or len(issues) > 0:
            return "medium"
        else:
            return "low"
    
    def _check_rule_conditions(self, rule: RoutingRule, factors: Dict[str, Any]) -> bool:
        """Check if rule conditions are met"""
        for key, expected_value in rule.conditions.items():
            if key in factors and factors[key] != expected_value:
                return False
        return True
    
    def _is_business_hours(self) -> bool:
        """Check if current time is within business hours"""
        now = datetime.now()
        weekday = now.weekday()
        hour = now.hour
        
        # Monday-Friday, 9 AM - 6 PM
        return weekday < 5 and 9 <= hour < 18
    
    async def _find_best_agent(
        self,
        skill_level: Optional[AgentSkillLevel],
        specialization: Optional[str],
        language: str
    ) -> Optional[str]:
        """Find best available agent based on criteria"""
        
        candidates = []
        
        for agent_id, agent in self.available_agents.items():
            # Check availability
            if not agent.is_available:
                continue
            
            # Check skill level
            if skill_level and agent.skill_level != skill_level:
                continue
            
            # Check specialization
            if specialization and specialization not in agent.specializations:
                continue
            
            # Check language
            if language not in agent.languages:
                continue
            
            candidates.append(agent)
        
        if not candidates:
            return None
        
        # Sort by performance and load
        candidates.sort(
            key=lambda a: (a.performance_score, -a.load_percentage),
            reverse=True
        )
        
        return candidates[0].agent_id
    
    async def _find_supervisor(self) -> Optional[str]:
        """Find available supervisor"""
        supervisors = [
            agent for agent in self.available_agents.values()
            if agent.skill_level == AgentSkillLevel.SUPERVISOR and agent.is_available
        ]
        
        if supervisors:
            return supervisors[0].agent_id
        return None
    
    async def _execute_routing(
        self,
        call_id: str,
        decision: RoutingDecision,
        target: Optional[str],
        payload: Dict[str, Any]
    ) -> None:
        """Execute routing decision"""
        
        self.active_routes[call_id] = {
            "decision": decision,
            "target": target,
            "timestamp": datetime.utcnow(),
            "status": "active"
        }
        
        if decision == RoutingDecision.AUTO_RESOLVE:
            await self._handle_auto_resolve(call_id, payload)
        
        elif decision == RoutingDecision.AGENT_TRANSFER:
            if target:
                await self._transfer_to_agent(call_id, target, payload)
                # Update agent load
                self.available_agents[target].current_load += 1
        
        elif decision == RoutingDecision.ESCALATE:
            if target:
                await self._escalate_to_supervisor(call_id, target, payload)
                self.available_agents[target].current_load += 1
        
        elif decision == RoutingDecision.CALLBACK:
            await self._schedule_callback(call_id, payload)
        
        elif decision == RoutingDecision.END_CALL:
            await self._end_call(call_id)
    
    async def _handle_auto_resolve(self, call_id: str, payload: Dict[str, Any]) -> None:
        """Handle auto-resolution"""
        message = Message(
            type=MessageType.ROUTING,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": call_id,
                "action": "auto_resolve",
                "resolution": payload.get("summary", {}).get("summary", ""),
                "confidence": payload.get("summary", {}).get("resolution_confidence", 0)
            }
        )
        
        await self.send_message(message)
        self.logger.info(f"Auto-resolved call {call_id}")
    
    async def _transfer_to_agent(self, call_id: str, agent_id: str, payload: Dict[str, Any]) -> None:
        """Transfer call to agent"""
        agent = self.available_agents[agent_id]
        
        message = Message(
            type=MessageType.ROUTING,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": call_id,
                "action": "transfer",
                "target_agent": agent_id,
                "agent_name": agent.name,
                "agent_skills": agent.specializations
            }
        )
        
        await self.send_message(message)
        self.logger.info(f"Transferred call {call_id} to agent {agent.name}")
    
    async def _escalate_to_supervisor(self, call_id: str, supervisor_id: str, payload: Dict[str, Any]) -> None:
        """Escalate call to supervisor"""
        supervisor = self.available_agents[supervisor_id]
        
        message = Message(
            type=MessageType.ROUTING,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": call_id,
                "action": "escalate",
                "target_supervisor": supervisor_id,
                "supervisor_name": supervisor.name,
                "escalation_reason": payload.get("escalation_reason", "Quality threshold not met")
            }
        )
        
        await self.send_message(message)
        self.logger.info(f"Escalated call {call_id} to supervisor {supervisor.name}")
    
    async def _schedule_callback(self, call_id: str, payload: Dict[str, Any]) -> None:
        """Schedule callback"""
        callback_time = datetime.utcnow() + timedelta(hours=1)
        
        message = Message(
            type=MessageType.ROUTING,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": call_id,
                "action": "callback",
                "scheduled_time": callback_time.isoformat(),
                "customer_phone": payload.get("metadata", {}).get("customer_phone")
            }
        )
        
        await self.send_message(message)
        self.logger.info(f"Scheduled callback for call {call_id} at {callback_time}")
    
    async def _end_call(self, call_id: str) -> None:
        """End call"""
        message = Message(
            type=MessageType.ROUTING,
            sender=self.name,
            recipient="system",
            payload={
                "call_id": call_id,
                "action": "end_call",
                "timestamp": datetime.utcnow().isoformat()
            }
        )
        
        await self.send_message(message)
        self.logger.info(f"Ended call {call_id}")
    
    async def _add_to_queue(self, call_id: str, metadata: Dict[str, Any], rule: RoutingRule) -> None:
        """Add call to queue"""
        self.queue.append({
            "call_id": call_id,
            "metadata": metadata,
            "rule": rule,
            "queued_at": datetime.utcnow()
        })
        
        self.logger.info(f"Added call {call_id} to queue (position: {len(self.queue)})")
    
    async def _monitor_queue(self) -> None:
        """Monitor and process queue"""
        while self._running:
            try:
                await self._process_queue()
                await asyncio.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error monitoring queue: {e}")
    
    async def _process_queue(self) -> None:
        """Process queued calls"""
        current_time = datetime.utcnow()
        processed = []
        
        for i, item in enumerate(self.queue):
            # Check if agent is now available
            target = await self._find_best_agent(
                item["rule"].target_skill_level,
                item["rule"].target_specialization,
                item["metadata"].get("language", "en")
            )
            
            if target:
                # Agent found, transfer call
                await self._transfer_to_agent(item["call_id"], target, item)
                processed.append(i)
            else:
                # Check if max queue time exceeded
                queue_time = (current_time - item["queued_at"]).total_seconds()
                if queue_time > self.max_queue_time:
                    # Schedule callback
                    await self._schedule_callback(item["call_id"], item)
                    processed.append(i)
        
        # Remove processed items
        for i in reversed(processed):
            self.queue.pop(i)
    
    async def _load_balancer(self) -> None:
        """Balance load across agents"""
        while self._running:
            try:
                # Redistribute calls if needed
                await self._redistribute_load()
                await asyncio.sleep(30)
                
            except Exception as e:
                self.logger.error(f"Error in load balancer: {e}")
    
    async def _redistribute_load(self) -> None:
        """Redistribute load across agents"""
        # Calculate average load
        total_load = sum(agent.current_load for agent in self.available_agents.values())
        total_capacity = sum(agent.max_capacity for agent in self.available_agents.values())
        
        if total_capacity > 0:
            avg_load_percentage = (total_load / total_capacity) * 100
            
            # Log load statistics
            self.logger.debug(f"System load: {avg_load_percentage:.1f}%")
    
    def _record_routing_decision(self, call_id: str, decision: RoutingDecision, target: Optional[str]) -> None:
        """Record routing decision for analytics"""
        self.routing_history.append({
            "call_id": call_id,
            "decision": decision.value,
            "target": target,
            "timestamp": datetime.utcnow().isoformat()
        })
    
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
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get system status"""
        return {
            "active_routes": len(self.active_routes),
            "queue_length": len(self.queue),
            "available_agents": sum(1 for a in self.available_agents.values() if a.is_available),
            "total_agents": len(self.available_agents),
            "routing_history_count": len(self.routing_history)
        }