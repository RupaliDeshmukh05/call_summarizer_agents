#!/usr/bin/env python3
"""Local development runner for Call Center AI System"""

import asyncio
import subprocess
import sys
import time
import os
import signal
from pathlib import Path
import psutil
import threading
from typing import List, Dict, Any

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config.settings import settings
from core import setup_logging, get_logger


class LocalRunner:
    """Local development environment runner"""
    
    def __init__(self):
        self.logger = get_logger(__name__)
        self.processes: Dict[str, subprocess.Popen] = {}
        self.running = False
        
        # Setup logging
        setup_logging(
            log_level="INFO",
            log_file="logs/local_runner.log",
            json_format=False
        )
    
    def check_dependencies(self) -> bool:
        """Check if required services are available"""
        self.logger.info("Checking dependencies...")
        
        dependencies = {
            "python": {"cmd": [sys.executable, "--version"], "required": True},
            "docker": {"cmd": ["docker", "--version"], "required": False},
            "postgresql": {"cmd": ["pg_isready", "-h", "localhost", "-p", "5432"], "required": False},
            "redis": {"cmd": ["redis-cli", "ping"], "required": False}
        }
        
        missing_required = []
        missing_optional = []
        
        for name, config in dependencies.items():
            try:
                result = subprocess.run(
                    config["cmd"], 
                    capture_output=True, 
                    text=True, 
                    timeout=5
                )
                if result.returncode == 0:
                    self.logger.info(f"✅ {name}: Available")
                else:
                    if config["required"]:
                        missing_required.append(name)
                    else:
                        missing_optional.append(name)
                        self.logger.warning(f"⚠️  {name}: Not available (optional)")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                if config["required"]:
                    missing_required.append(name)
                    self.logger.error(f"❌ {name}: Not found (required)")
                else:
                    missing_optional.append(name)
                    self.logger.warning(f"⚠️  {name}: Not found (optional)")
        
        if missing_required:
            self.logger.error(f"Missing required dependencies: {missing_required}")
            return False
        
        if missing_optional:
            self.logger.info("Some optional services are missing. Using fallback configurations.")
        
        return True
    
    def setup_environment(self):
        """Setup local environment"""
        self.logger.info("Setting up local environment...")
        
        # Create necessary directories
        dirs_to_create = [
            "logs",
            "static", 
            "templates",
            "data"
        ]
        
        for dir_name in dirs_to_create:
            Path(dir_name).mkdir(exist_ok=True)
            self.logger.info(f"Created directory: {dir_name}")
        
        # Install Python dependencies
        self.logger.info("Installing Python dependencies...")
        try:
            subprocess.run([
                sys.executable, "-m", "pip", "install", "-r", "requirements.txt"
            ], check=True)
            self.logger.info("✅ Python dependencies installed")
        except subprocess.CalledProcessError as e:
            self.logger.error(f"❌ Failed to install dependencies: {e}")
            return False
        
        return True
    
    def start_mock_services(self):
        """Start mock services for local development"""
        self.logger.info("Starting mock services...")
        
        # Check if we need to start Docker services
        if not self._is_service_available("postgresql", "localhost", 5432):
            self.logger.info("PostgreSQL not found, attempting to start with Docker...")
            self._start_docker_postgres()
        
        if not self._is_service_available("redis", "localhost", 6379):
            self.logger.info("Redis not found, attempting to start with Docker...")
            self._start_docker_redis()
    
    def _is_service_available(self, service_name: str, host: str, port: int) -> bool:
        """Check if a service is available on given host:port"""
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                sock.settimeout(2)
                result = sock.connect_ex((host, port))
                return result == 0
        except:
            return False
    
    def _start_docker_postgres(self):
        """Start PostgreSQL with Docker"""
        try:
            cmd = [
                "docker", "run", "-d",
                "--name", "callcenter_postgres_dev",
                "-e", "POSTGRES_DB=call_center_db",
                "-e", "POSTGRES_USER=callcenter", 
                "-e", "POSTGRES_PASSWORD=callcenter_pass",
                "-p", "5432:5432",
                "postgres:15-alpine"
            ]
            
            # Check if container already exists
            check_cmd = ["docker", "ps", "-a", "--filter", "name=callcenter_postgres_dev", "--format", "{{.Names}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            if "callcenter_postgres_dev" in result.stdout:
                # Container exists, start it
                subprocess.run(["docker", "start", "callcenter_postgres_dev"], check=True)
                self.logger.info("✅ Started existing PostgreSQL container")
            else:
                # Create new container
                subprocess.run(cmd, check=True)
                self.logger.info("✅ Created and started PostgreSQL container")
            
            # Wait for PostgreSQL to be ready
            for i in range(30):
                if self._is_service_available("postgresql", "localhost", 5432):
                    break
                time.sleep(1)
            
        except subprocess.CalledProcessError:
            self.logger.warning("⚠️  Could not start PostgreSQL with Docker. Using SQLite fallback.")
            # Update settings to use SQLite
            os.environ["DATABASE_URL"] = "sqlite:///./call_center.db"
    
    def _start_docker_redis(self):
        """Start Redis with Docker"""
        try:
            cmd = [
                "docker", "run", "-d",
                "--name", "callcenter_redis_dev",
                "-p", "6379:6379",
                "redis:7-alpine"
            ]
            
            # Check if container already exists
            check_cmd = ["docker", "ps", "-a", "--filter", "name=callcenter_redis_dev", "--format", "{{.Names}}"]
            result = subprocess.run(check_cmd, capture_output=True, text=True)
            
            if "callcenter_redis_dev" in result.stdout:
                subprocess.run(["docker", "start", "callcenter_redis_dev"], check=True)
                self.logger.info("✅ Started existing Redis container")
            else:
                subprocess.run(cmd, check=True)
                self.logger.info("✅ Created and started Redis container")
            
            # Wait for Redis to be ready
            for i in range(10):
                if self._is_service_available("redis", "localhost", 6379):
                    break
                time.sleep(1)
                
        except subprocess.CalledProcessError:
            self.logger.warning("⚠️  Could not start Redis with Docker. Disabling Redis features.")
            os.environ["REDIS_URL"] = ""
    
    def start_application(self, component: str = "all"):
        """Start application components"""
        self.logger.info(f"Starting application component: {component}")
        self.running = True
        
        try:
            if component == "all":
                self._start_all_components()
            elif component == "api":
                self._start_api_server()
            elif component == "dashboard":
                self._start_dashboard()
            elif component == "agents":
                self._start_agents()
            else:
                self.logger.error(f"Unknown component: {component}")
                return False
            
            # Setup signal handlers
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
            
            # Keep running
            self._monitor_processes()
            
        except KeyboardInterrupt:
            self.logger.info("Received interrupt signal")
        finally:
            self.stop_application()
    
    def _start_all_components(self):
        """Start all application components"""
        components = [
            ("agents", [sys.executable, "main.py", "system"]),
            ("api", [sys.executable, "main.py", "api", "--reload"]),
            ("dashboard", [sys.executable, "main.py", "dashboard"])
        ]
        
        for name, cmd in components:
            try:
                self.logger.info(f"Starting {name}...")
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    universal_newlines=True
                )
                self.processes[name] = process
                
                # Start log monitoring thread
                thread = threading.Thread(
                    target=self._monitor_process_output,
                    args=(name, process),
                    daemon=True
                )
                thread.start()
                
                # Give each component time to start
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Failed to start {name}: {e}")
    
    def _start_api_server(self):
        """Start only the API server"""
        cmd = [sys.executable, "main.py", "api", "--reload", "--port", "8000"]
        process = subprocess.Popen(cmd)
        self.processes["api"] = process
        self.logger.info("API server started at http://localhost:8000")
    
    def _start_dashboard(self):
        """Start only the dashboard"""
        cmd = [sys.executable, "main.py", "dashboard"]
        process = subprocess.Popen(cmd)
        self.processes["dashboard"] = process
        self.logger.info("Dashboard started at http://localhost:8501")
    
    def _start_agents(self):
        """Start only the agent system"""
        cmd = [sys.executable, "main.py", "system"]
        process = subprocess.Popen(cmd)
        self.processes["agents"] = process
        self.logger.info("Agent system started")
    
    def _monitor_process_output(self, name: str, process: subprocess.Popen):
        """Monitor process output and log it"""
        try:
            for line in iter(process.stdout.readline, ''):
                if line:
                    self.logger.info(f"[{name}] {line.strip()}")
        except Exception as e:
            self.logger.error(f"Error monitoring {name}: {e}")
    
    def _monitor_processes(self):
        """Monitor running processes"""
        while self.running:
            try:
                # Check if processes are still running
                dead_processes = []
                for name, process in self.processes.items():
                    if process.poll() is not None:
                        dead_processes.append(name)
                        self.logger.warning(f"Process {name} has stopped")
                
                # Remove dead processes
                for name in dead_processes:
                    del self.processes[name]
                
                # If all processes are dead, stop
                if not self.processes and self.running:
                    self.logger.info("All processes have stopped")
                    break
                
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error monitoring processes: {e}")
                break
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def stop_application(self):
        """Stop all application components"""
        self.logger.info("Stopping application...")
        self.running = False
        
        # Stop all processes
        for name, process in self.processes.items():
            try:
                self.logger.info(f"Stopping {name}...")
                process.terminate()
                
                # Wait for process to stop
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self.logger.warning(f"Force killing {name}...")
                    process.kill()
                    
            except Exception as e:
                self.logger.error(f"Error stopping {name}: {e}")
        
        self.processes.clear()
        self.logger.info("Application stopped")
    
    def print_startup_info(self):
        """Print startup information"""
        print("\n" + "="*60)
        print("🚀 AI Call Center System - Local Development")
        print("="*60)
        print(f"📂 Project Directory: {Path.cwd()}")
        print(f"🐍 Python Version: {sys.version}")
        print(f"🔧 Environment: {os.getenv('ENVIRONMENT', 'development')}")
        print("\n📋 Available Services:")
        print("   • API Server:     http://localhost:8000")
        print("   • Dashboard:      http://localhost:8501") 
        print("   • API Docs:       http://localhost:8000/docs")
        print("   • Health Check:   http://localhost:8000/health")
        print("\n📊 Monitoring:")
        print("   • Logs:           tail -f logs/call_center.log")
        print("   • System Status:  python main.py status")
        print("\n⌨️  Commands:")
        print("   • Stop:           Ctrl+C")
        print("   • Restart:        python run_local.py")
        print("="*60 + "\n")


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run AI Call Center System Locally")
    parser.add_argument(
        "--component", 
        choices=["all", "api", "dashboard", "agents"],
        default="all",
        help="Component to run (default: all)"
    )
    parser.add_argument(
        "--setup", 
        action="store_true",
        help="Setup environment and install dependencies"
    )
    
    args = parser.parse_args()
    
    runner = LocalRunner()
    
    try:
        # Print startup info
        runner.print_startup_info()
        
        # Check dependencies
        if not runner.check_dependencies():
            print("❌ Dependency check failed. Please install required dependencies.")
            return 1
        
        # Setup environment if requested
        if args.setup:
            if not runner.setup_environment():
                print("❌ Environment setup failed.")
                return 1
        
        # Start mock services
        runner.start_mock_services()
        
        # Wait a bit for services to start
        print("⏳ Starting services...")
        time.sleep(3)
        
        # Start application
        runner.start_application(args.component)
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0


if __name__ == "__main__":
    sys.exit(main())