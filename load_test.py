#!/usr/bin/env python3
"""Load testing script for the AI Call Center API"""

import requests
import threading
import time
import random

BASE_URL = "http://localhost:8000"

def create_test_call(call_number):
    """Create a test call"""
    call_data = {
        "customer_phone": f"+1-555-{random.randint(1000, 9999)}",
        "priority": random.choice(["low", "normal", "high"]),
        "metadata": {
            "test_call": True,
            "call_number": call_number,
            "timestamp": time.time()
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/calls", json=call_data)
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Call {call_number}: {result['call']['call_id']}")
        else:
            print(f"❌ Call {call_number}: Failed ({response.status_code})")
    except Exception as e:
        print(f"❌ Call {call_number}: Error - {e}")

def load_test(num_calls=10, num_threads=5):
    """Run load test with multiple concurrent calls"""
    print(f"🚀 Starting load test: {num_calls} calls with {num_threads} threads")
    print("-" * 50)
    
    start_time = time.time()
    threads = []
    
    # Create calls in batches
    for i in range(0, num_calls, num_threads):
        batch_threads = []
        for j in range(min(num_threads, num_calls - i)):
            call_num = i + j + 1
            thread = threading.Thread(target=create_test_call, args=(call_num,))
            batch_threads.append(thread)
            thread.start()
        
        # Wait for batch to complete
        for thread in batch_threads:
            thread.join()
        
        time.sleep(0.1)  # Small delay between batches
    
    end_time = time.time()
    print(f"\n⏱️ Load test completed in {end_time - start_time:.2f} seconds")

if __name__ == "__main__":
    load_test(20, 5)  # Create 20 calls with 5 concurrent threads