#!/bin/bash

# AI Call Center System - Local Startup Script

set -e

echo "🚀 Starting AI Call Center System Locally"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "main.py" ] || [ ! -f "requirements.txt" ]; then
    print_error "Please run this script from the call_summarizer_agents directory"
    exit 1
fi

# Check Python version
python_version=$(python3 --version 2>&1 | cut -d' ' -f2)
required_version="3.11"

if ! python3 -c "import sys; exit(0 if sys.version_info >= (3, 11) else 1)" 2>/dev/null; then
    print_error "Python 3.11+ is required. Found: $python_version"
    exit 1
else
    print_success "Python version: $python_version"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    print_status "Creating virtual environment..."
    python3 -m venv venv
    print_success "Virtual environment created"
fi

# Activate virtual environment
print_status "Activating virtual environment..."
source venv/bin/activate

# Install requirements
print_status "Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt

# Create necessary directories
print_status "Creating directories..."
mkdir -p logs static templates data

# Copy environment file if it doesn't exist
if [ ! -f ".env" ]; then
    print_status "Creating .env file..."
    cp .env.example .env
    print_warning "Please edit .env file with your API keys before running the system"
fi

# Function to check if a port is in use
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null ; then
        return 0
    else
        return 1
    fi
}

# Function to start a service in the background
start_service() {
    local service_name=$1
    local command=$2
    local port=$3
    local log_file="logs/${service_name}.log"
    
    print_status "Starting $service_name..."
    
    # Check if port is already in use
    if check_port $port; then
        print_warning "$service_name port $port is already in use"
        return 1
    fi
    
    # Start service
    nohup $command > "$log_file" 2>&1 &
    local pid=$!
    
    # Save PID for later cleanup
    echo $pid > "logs/${service_name}.pid"
    
    # Wait a moment and check if service started successfully
    sleep 2
    if kill -0 $pid 2>/dev/null; then
        print_success "$service_name started (PID: $pid, Port: $port)"
        return 0
    else
        print_error "$service_name failed to start"
        return 1
    fi
}

# Function to check if Docker is available and start services
start_docker_services() {
    if command -v docker >/dev/null 2>&1; then
        print_status "Docker found. Starting database services..."
        
        # Start PostgreSQL
        if ! docker ps --format "table {{.Names}}" | grep -q callcenter_postgres_dev; then
            print_status "Starting PostgreSQL container..."
            docker run -d \
                --name callcenter_postgres_dev \
                -e POSTGRES_DB=call_center_db \
                -e POSTGRES_USER=callcenter \
                -e POSTGRES_PASSWORD=callcenter_pass \
                -p 5432:5432 \
                postgres:15-alpine >/dev/null 2>&1
            
            # Wait for PostgreSQL to be ready
            print_status "Waiting for PostgreSQL to be ready..."
            for i in {1..30}; do
                if docker exec callcenter_postgres_dev pg_isready -U callcenter >/dev/null 2>&1; then
                    print_success "PostgreSQL is ready"
                    break
                fi
                sleep 1
            done
        else
            docker start callcenter_postgres_dev >/dev/null 2>&1
            print_success "PostgreSQL container started"
        fi
        
        # Start Redis
        if ! docker ps --format "table {{.Names}}" | grep -q callcenter_redis_dev; then
            print_status "Starting Redis container..."
            docker run -d \
                --name callcenter_redis_dev \
                -p 6379:6379 \
                redis:7-alpine >/dev/null 2>&1
            print_success "Redis container started"
        else
            docker start callcenter_redis_dev >/dev/null 2>&1
            print_success "Redis container started"
        fi
        
    else
        print_warning "Docker not found. Database services will use fallback configuration."
        # Update environment to use SQLite
        sed -i.bak 's|DATABASE_URL=postgresql.*|DATABASE_URL=sqlite:///./call_center.db|' .env
        sed -i.bak 's|REDIS_URL=redis.*|REDIS_URL=|' .env
    fi
}

# Function to stop all services
stop_services() {
    print_status "Stopping services..."
    
    # Kill processes using PID files
    for pid_file in logs/*.pid; do
        if [ -f "$pid_file" ]; then
            pid=$(cat "$pid_file")
            service_name=$(basename "$pid_file" .pid)
            
            if kill -0 $pid 2>/dev/null; then
                print_status "Stopping $service_name (PID: $pid)..."
                kill $pid
                sleep 2
                
                # Force kill if still running
                if kill -0 $pid 2>/dev/null; then
                    kill -9 $pid
                fi
            fi
            
            rm -f "$pid_file"
        fi
    done
    
    # Stop Docker containers
    if command -v docker >/dev/null 2>&1; then
        docker stop callcenter_postgres_dev callcenter_redis_dev >/dev/null 2>&1 || true
    fi
    
    print_success "All services stopped"
}

# Trap to cleanup on exit
trap stop_services EXIT INT TERM

# Parse command line arguments
COMPONENT="all"
SETUP_ENV=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --component)
            COMPONENT="$2"
            shift 2
            ;;
        --setup)
            SETUP_ENV=true
            shift
            ;;
        --help)
            echo "Usage: $0 [--component all|api|dashboard|agents] [--setup]"
            echo ""
            echo "Options:"
            echo "  --component   Component to run (all, api, dashboard, agents)"
            echo "  --setup       Setup environment and install dependencies"
            echo "  --help        Show this help message"
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Main execution
print_status "Component to run: $COMPONENT"

# Start Docker services if available
start_docker_services

# Start application components
case $COMPONENT in
    "all")
        print_status "Starting all components..."
        start_service "api" "python main.py api --reload" 8000
        sleep 3
        start_service "dashboard" "python main.py dashboard" 8501
        sleep 3
        start_service "agents" "python main.py system" 0
        ;;
    "api")
        start_service "api" "python main.py api --reload" 8000
        ;;
    "dashboard")
        start_service "dashboard" "python main.py dashboard" 8501
        ;;
    "agents")
        start_service "agents" "python main.py system" 0
        ;;
    *)
        print_error "Unknown component: $COMPONENT"
        exit 1
        ;;
esac

# Print access information
echo ""
echo "🎉 AI Call Center System Started Successfully!"
echo "=============================================="
echo ""
echo "📋 Service URLs:"
echo "   • API Server:     http://localhost:8000"
echo "   • API Docs:       http://localhost:8000/docs"
echo "   • Dashboard:      http://localhost:8501"
echo "   • Health Check:   http://localhost:8000/health"
echo ""
echo "📊 Monitoring:"
echo "   • API Logs:       tail -f logs/api.log"
echo "   • Dashboard Logs: tail -f logs/dashboard.log"
echo "   • Agent Logs:     tail -f logs/agents.log"
echo ""
echo "⌨️  Commands:"
echo "   • Stop Services:  Ctrl+C"
echo "   • View Logs:      ls logs/"
echo "   • Check Status:   curl http://localhost:8000/health"
echo ""

# Wait for user interrupt
print_status "Services running. Press Ctrl+C to stop..."
while true; do
    sleep 1
done