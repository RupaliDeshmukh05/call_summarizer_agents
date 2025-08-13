# AI Call Center Multi-Agent System

A sophisticated multi-agent AI system for call center operations featuring real-time transcription, intelligent summarization, quality scoring, and automated routing.

## 🏗️ Architecture Overview

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Call Intake   │    │  Transcription  │    │ Summarization   │
│     Agent       │───▶│     Agent       │───▶│     Agent       │
│                 │    │  (Deepgram/     │    │   (GPT-4)       │
│                 │    │   Whisper)      │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │              ┌─────────────────┐              │
         │              │  Message Bus    │              │
         │              │ (RabbitMQ/Redis)│              │
         │              └─────────────────┘              │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  Routing Agent  │    │ Quality Score   │    │   Database      │
│                 │    │     Agent       │    │ (PostgreSQL)    │
│                 │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## ✨ Features

### 🤖 Multi-Agent Architecture
- **Intake Agent**: Handles initial call reception and metadata extraction
- **Transcription Agent**: Real-time speech-to-text with speaker diarization
- **Summarization Agent**: Intelligent call summarization and key point extraction
- **Quality Scoring Agent**: Automated quality assessment with structured rubrics
- **Routing Agent**: Smart call routing and escalation management

### 🔊 Voice Integration
- **Twilio Integration**: Full telephony support for inbound/outbound calls
- **Deepgram/Whisper**: Real-time transcription with high accuracy
- **Speaker Diarization**: Automatic speaker identification and separation
- **Multi-language Support**: Transcription in multiple languages

### 📊 Real-time Dashboard
- **Live Call Monitoring**: View active calls and agent status
- **Quality Metrics**: Real-time quality scores and compliance tracking
- **Performance Analytics**: Comprehensive reporting and insights
- **Agent Management**: Monitor agent performance and workload

### 🔄 Intelligent Routing
- **Skill-based Routing**: Match customers with appropriate agents
- **Load Balancing**: Distribute calls efficiently across agents
- **Auto-escalation**: Automatic escalation based on quality thresholds
- **Queue Management**: Smart queue handling with priority routing

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Docker and Docker Compose
- PostgreSQL
- Redis
- RabbitMQ (optional)

### Environment Setup

1. **Clone the repository**
```bash
git clone <repository-url>
cd call_summarizer_agents
```

2. **Copy environment configuration**
```bash
cp .env.example .env
```

3. **Configure your environment variables**
```bash
# Required API Keys
OPENAI_API_KEY=your_openai_api_key_here
DEEPGRAM_API_KEY=your_deepgram_api_key_here
TWILIO_ACCOUNT_SID=your_twilio_account_sid
TWILIO_AUTH_TOKEN=your_twilio_auth_token
TWILIO_PHONE_NUMBER=+1234567890

# Database
DATABASE_URL=postgresql://callcenter:callcenter_pass@localhost:5432/call_center_db
REDIS_URL=redis://localhost:6379/0

# Security
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key
```

### 🐳 Docker Deployment (Recommended)

**Start the complete system:**
```bash
docker-compose up -d
```

**For development with hot reload:**
```bash
docker-compose -f docker-compose.yml -f docker-compose.override.yml up -d
```

**Access the services:**
- API: http://localhost:8000
- Dashboard: http://localhost:8501
- RabbitMQ Management: http://localhost:15672 (callcenter/callcenter_pass)
- Grafana: http://localhost:3000 (admin/admin)
- Prometheus: http://localhost:9090

### 🖥️ Local Development

**Install dependencies:**
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt  # For development
```

**Start services individually:**

1. **Start the complete system:**
```bash
python main.py system
```

2. **Start individual services:**
```bash
# API Server
python main.py api --host 0.0.0.0 --port 8000 --reload

# Dashboard
python main.py dashboard

# Individual agent
python main.py agent --agent IntakeAgent
```

## 📋 Usage Examples

### 1. Processing an Incoming Call

```python
from agents.intake_agent import IntakeAgent
from core import AgentConfig

# Initialize intake agent
config = AgentConfig(
    name="IntakeAgent",
    type="intake",
    custom_config={
        "company_name": "AI Call Center",
        "enable_telephony": True
    }
)

agent = IntakeAgent(config)
await agent.initialize()
await agent.start()
```

### 2. Real-time Transcription

```python
from agents.transcription_agent import TranscriptionAgent

# Configure for Deepgram
config = AgentConfig(
    name="TranscriptionAgent",
    type="transcription", 
    custom_config={
        "provider": "deepgram",
        "deepgram_api_key": "your_key",
        "language": "en",
        "enable_diarization": True
    }
)

agent = TranscriptionAgent(config)
```

### 3. Quality Assessment

```python
from agents.quality_score_agent import QualityScoringAgent

agent = QualityScoringAgent(AgentConfig(
    name="QualityScoringAgent",
    type="quality_scoring"
))

# Agent will automatically score calls based on:
# - Greeting quality
# - Identity verification
# - Issue understanding
# - Solution effectiveness
# - Professionalism
# - Compliance
```

### 4. API Usage

**Create a call:**
```bash
curl -X POST "http://localhost:8000/api/v1/calls" \
  -H "Content-Type: application/json" \
  -d '{
    "customer_phone": "+1234567890",
    "priority": "normal",
    "metadata": {
      "customer_name": "John Doe"
    }
  }'
```

**Get call status:**
```bash
curl "http://localhost:8000/api/v1/calls/{call_id}"
```

## 🧪 Testing

**Run all tests:**
```bash
python main.py test
```

**Run specific test categories:**
```bash
# Unit tests
pytest tests/unit/ -v

# Integration tests  
pytest tests/integration/ -v

# Coverage report
pytest --cov=. --cov-report=html
```

## 📊 Monitoring & Analytics

### Prometheus Metrics
- Call volume and duration
- Agent performance metrics
- Quality score distributions
- System resource usage

### Grafana Dashboards
- Real-time call center overview
- Agent performance tracking
- Quality trends analysis
- System health monitoring

### Built-in Analytics
- Call outcome analysis
- Customer satisfaction prediction
- Agent coaching recommendations
- ROI and cost analysis

## 🔧 Configuration

### Agent Configuration

Each agent can be configured via the `AgentConfig` class:

```python
config = AgentConfig(
    name="AgentName",
    type="agent_type",
    max_retries=3,
    timeout_seconds=300,
    enable_metrics=True,
    custom_config={
        # Agent-specific configuration
    }
)
```

### Message Bus Configuration

Support for multiple message brokers:
- **RabbitMQ**: Production-grade message queuing
- **Redis**: High-performance pub/sub
- **Memory**: In-memory for testing

### Database Configuration

**PostgreSQL Models:**
- Calls, Customers, Agents
- Transcripts, Summaries, Quality Assessments
- Routing Decisions, System Metrics

## 🔐 Security

- **Authentication**: JWT-based API authentication
- **Authorization**: Role-based access control
- **Data Privacy**: Secure handling of call recordings and transcripts
- **Compliance**: Configurable compliance rules and monitoring

## 🚀 Deployment

### Production Deployment

1. **Environment Variables**: Set all required environment variables
2. **SSL/TLS**: Configure SSL certificates for secure communication
3. **Scaling**: Use Docker Swarm or Kubernetes for horizontal scaling
4. **Monitoring**: Set up comprehensive monitoring and alerting
5. **Backup**: Configure database backups and disaster recovery

### Cloud Deployment Options

- **AWS**: ECS, EKS, or EC2 with RDS and ElastiCache
- **Google Cloud**: GKE with Cloud SQL and Memorystore
- **Azure**: AKS with Azure Database and Redis Cache

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

### Development Guidelines

- Follow PEP 8 style guidelines
- Write comprehensive tests
- Update documentation
- Use type hints
- Follow the existing architecture patterns

## 📝 API Documentation

### REST API Endpoints

**Calls:**
- `POST /api/v1/calls` - Create new call
- `GET /api/v1/calls/{id}` - Get call details
- `PUT /api/v1/calls/{id}` - Update call
- `GET /api/v1/calls` - List calls

**Agents:**
- `GET /api/v1/agents` - List agents
- `GET /api/v1/agents/{id}` - Get agent details
- `POST /api/v1/agents/{id}/status` - Update agent status

**Quality:**
- `GET /api/v1/quality/{call_id}` - Get quality assessment
- `GET /api/v1/quality/reports` - Quality reports

**Analytics:**
- `GET /api/v1/analytics/calls` - Call analytics
- `GET /api/v1/analytics/agents` - Agent performance
- `GET /api/v1/analytics/quality` - Quality metrics

### WebSocket Endpoints

**Real-time Features:**
- `/ws/calls/{call_id}` - Live call updates
- `/ws/transcription/{call_id}` - Real-time transcription
- `/ws/dashboard` - Dashboard updates

## 🆘 Troubleshooting

### Common Issues

**1. Database Connection Issues**
```bash
# Check PostgreSQL connection
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up postgres -d
```

**2. Agent Communication Issues**
```bash
# Check message bus status
docker-compose logs rabbitmq redis

# Restart message services
docker-compose restart rabbitmq redis
```

**3. Transcription Not Working**
- Verify Deepgram API key
- Check audio format compatibility
- Monitor transcription agent logs

**4. Quality Scoring Issues**
- Ensure OpenAI API key is valid
- Check quality scoring agent logs
- Verify transcript completeness

### Log Analysis

**View system logs:**
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f transcription_agent

# Filter by level
docker-compose logs | grep ERROR
```

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **OpenAI**: For GPT models used in summarization
- **Deepgram**: For real-time transcription services
- **Twilio**: For telephony integration
- **FastAPI**: For the robust API framework
- **Streamlit**: For the interactive dashboard

## 📞 Support

For support and questions:
- Create an issue in this repository
- Check the documentation
- Review the troubleshooting guide

---

**Built with ❤️ for better customer service experiences**