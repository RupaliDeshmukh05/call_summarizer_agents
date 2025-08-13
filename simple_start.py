#!/usr/bin/env python3
"""Simple startup script that runs just the API server"""

import sys
import os
import uvicorn
from pathlib import Path

# Add project root to Python path
sys.path.insert(0, str(Path(__file__).resolve().parent))

def main():
    """Simple API server startup"""
    print("🚀 Starting AI Call Center API Server")
    print("=" * 50)
    
    # Set environment for local development
    os.environ.setdefault("ENVIRONMENT", "development")
    os.environ.setdefault("DEBUG", "true")
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./call_center.db")
    
    try:
        # Run the API server directly
        uvicorn.run(
            "api.main:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    sys.exit(main())