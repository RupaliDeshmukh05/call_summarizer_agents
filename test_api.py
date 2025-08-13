#!/usr/bin/env python3
"""Test script for the AI Call Center API"""

import requests
import json
import time

BASE_URL = "http://localhost:8000"

def test_health():
    """Test health endpoint"""
    print("🔍 Testing health endpoint...")
    response = requests.get(f"{BASE_URL}/health")
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    print()

def test_system_status():
    """Test system status"""
    print("🔍 Testing system status...")
    response = requests.get(f"{BASE_URL}/api/v1/status")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_create_call():
    """Test creating a new call"""
    print("🔍 Testing call creation...")
    call_data = {
        "customer_phone": "+1-555-0123",
        "priority": "high",
        "metadata": {
            "source": "mobile_app",
            "customer_tier": "premium"
        }
    }
    
    response = requests.post(f"{BASE_URL}/api/v1/calls", json=call_data)
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    
    if result.get("success"):
        call_id = result["call"]["call_id"]
        print(f"✅ Created call with ID: {call_id}")
        return call_id
    print()

def test_get_call(call_id):
    """Test getting call details"""
    print(f"🔍 Testing get call details for {call_id}...")
    response = requests.get(f"{BASE_URL}/api/v1/calls/{call_id}")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_list_calls():
    """Test listing calls"""
    print("🔍 Testing list calls...")
    response = requests.get(f"{BASE_URL}/api/v1/calls?limit=5")
    print(f"Status: {response.status_code}")
    result = response.json()
    print(f"Found {result.get('total', 0)} calls")
    print(f"Response: {json.dumps(result, indent=2)}")
    print()

def test_list_agents():
    """Test listing agents"""
    print("🔍 Testing list agents...")
    response = requests.get(f"{BASE_URL}/api/v1/agents")
    print(f"Status: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print()

def test_dashboard_analytics():
    """Test dashboard analytics"""
    print("🔍 Testing dashboard analytics...")
    response = requests.get(f"{BASE_URL}/api/v1/analytics/dashboard")
    print(f"Status: {response.status_code}")
    result = response.json()
    if result.get("success"):
        data = result["data"]
        print(f"Active calls: {data['metrics']['active_calls']}")
        print(f"Available agents: {data['metrics']['available_agents']}")
        print(f"Average quality score: {data['metrics']['average_quality_score']}")
        print(f"Recent activity: {len(data['recent_activity'])} events")
    print()

def main():
    """Run all tests"""
    print("🚀 Testing AI Call Center System API")
    print("=" * 50)
    
    try:
        # Basic health checks
        test_health()
        test_system_status()
        
        # Call management
        call_id = test_create_call()
        if call_id:
            test_get_call(call_id)
        
        test_list_calls()
        
        # Agent management
        test_list_agents()
        
        # Analytics
        test_dashboard_analytics()
        
        print("✅ All tests completed!")
        
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to the API server.")
        print("Make sure the server is running at http://localhost:8000")
    except Exception as e:
        print(f"❌ Error during testing: {e}")

if __name__ == "__main__":
    main()