#!/usr/bin/env python3
"""Quick start script for local development"""

import subprocess
import sys
import os
import time
import threading
from pathlib import Path

def install_dependencies():
    """Install minimal dependencies"""
    print("📦 Installing dependencies...")
    try:
        subprocess.run([
            sys.executable, "-m", "pip", "install", "-r", "requirements-minimal.txt"
        ], check=True)
        print("✅ Dependencies installed")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def start_api_server():
    """Start the API server"""
    print("🚀 Starting API server...")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path.cwd())
    
    process = subprocess.Popen([
        sys.executable, "-m", "uvicorn", "api.main:app",
        "--host", "0.0.0.0", 
        "--port", "8000",
        "--reload"
    ], env=env)
    
    return process

def start_dashboard():
    """Start the dashboard"""
    print("📊 Starting dashboard...")
    env = os.environ.copy() 
    env["PYTHONPATH"] = str(Path.cwd())
    
    process = subprocess.Popen([
        sys.executable, "-m", "streamlit", "run", "frontend/dashboard.py",
        "--server.port", "8501",
        "--server.address", "0.0.0.0"
    ], env=env)
    
    return process

def main():
    """Main function"""
    print("🤖 AI Call Center System - Quick Start")
    print("=" * 50)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ required")
        return 1
    
    # Install dependencies
    if not install_dependencies():
        return 1
    
    # Create directories
    Path("logs").mkdir(exist_ok=True)
    
    processes = []
    
    try:
        # Start API server
        api_process = start_api_server()
        processes.append(("API", api_process))
        time.sleep(3)
        
        # Start dashboard
        dashboard_process = start_dashboard()
        processes.append(("Dashboard", dashboard_process))
        time.sleep(2)
        
        print("\n🎉 System Started Successfully!")
        print("=" * 50)
        print("📋 Access URLs:")
        print("   • API Server:   http://localhost:8000")
        print("   • API Docs:     http://localhost:8000/docs") 
        print("   • Dashboard:    http://localhost:8501")
        print("   • Health Check: http://localhost:8000/health")
        print("\n⌨️  Press Ctrl+C to stop")
        print("=" * 50)
        
        # Wait for interrupt
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n🛑 Stopping services...")
        
        for name, process in processes:
            try:
                print(f"Stopping {name}...")
                process.terminate()
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
            except Exception as e:
                print(f"Error stopping {name}: {e}")
        
        print("✅ All services stopped")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())