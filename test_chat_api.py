"""
Quick test script for the Chat API
This demonstrates how to use the natural language query interface
"""

import requests
import json

# API Configuration
BASE_URL = "http://localhost:8000"

def login():
    """Login and get access token"""
    response = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"username": "admin", "password": "admin"}
    )
    if response.status_code == 200:
        token = response.json()["access_token"]
        print("✅ Login successful!")
        return token
    else:
        print(f"❌ Login failed: {response.text}")
        return None

def chat_query(token, query):
    """Send a natural language query to the chat API"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    response = requests.post(
        f"{BASE_URL}/api/query/chat",
        headers=headers,
        json={"query": query}
    )
    
    if response.status_code == 200:
        result = response.json()
        print(f"\n🔍 Query: {query}")
        print(f"⏱️  Execution time: {result['execution_time']:.3f} seconds")
        print(f"📊 Results:")
        print(json.dumps(result['results'], indent=2))
        return result
    else:
        print(f"❌ Query failed: {response.text}")
        return None

def main():
    print("=" * 60)
    print("🤖 vMiner Chat API - Natural Language Query Demo")
    print("=" * 60)
    
    # Login
    token = login()
    if not token:
        return
    
    # Example queries with spelling mistakes to demonstrate fuzzy matching
    queries = [
        "get all powered on VMs",
        "show me hosts with no vms",
        "get all empty datastores",
        # With typos - the system will correct them!
        "shoe me all powred on vms",
        "get all emty datastors",
    ]
    
    print("\n" + "=" * 60)
    print("📝 Note: The database might be empty if you haven't run sync yet.")
    print("   To populate data, run: python setup.py")
    print("   Then trigger sync via: POST /api/vcenters/sync")
    print("=" * 60)
    
    for query in queries:
        chat_query(token, query)
        print("\n" + "-" * 60)

if __name__ == "__main__":
    main()
