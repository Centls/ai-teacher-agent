import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_api():
    print("Waiting for server to start...")
    time.sleep(5) # Give uvicorn time to boot
    
    # 1. Test Health
    try:
        resp = requests.get(f"{BASE_URL}/")
        print(f"Health Check: {resp.status_code} - {resp.json()}")
    except Exception as e:
        print(f"Health Check Failed: {e}")
        sys.exit(1)

    # 2. Test Status
    resp = requests.get(f"{BASE_URL}/status")
    print(f"Status Check: {resp.status_code} - {resp.json()}")
    
    # 3. Test Query
    query_text = "TCM手表原理"
    print(f"\n--- Sending Query: '{query_text}' ---")
    payload = {"query": query_text, "k": 2}
    
    resp = requests.post(f"{BASE_URL}/query", json=payload)
    print(f"Query Check: {resp.status_code}")
    
    if resp.status_code == 200:
        print(f"Query Result (Full):\n{resp.json()['result']}")
    else:
        print(f"Query Error: {resp.text}")

if __name__ == "__main__":
    test_api()
