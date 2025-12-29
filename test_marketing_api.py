import requests
import json
import sys

BASE_URL = "http://localhost:8002"

def test_chat_stream():
    print("Testing /chat/stream...")
    url = f"{BASE_URL}/chat/stream"
    payload = {
        "question": "如何制定一个品牌营销策略？",
        "thread_id": "test_thread_001"
    }
    
    try:
        with requests.post(url, json=payload, stream=True) as response:
            if response.status_code == 200:
                print("Stream started successfully.")
                for line in response.iter_lines():
                    if line:
                        decoded_line = line.decode('utf-8')
                        if decoded_line.startswith("data: "):
                            data_str = decoded_line[6:]
                            try:
                                data = json.loads(data_str)
                                if data.get("type") == "token":
                                    print(data["content"], end="", flush=True)
                                elif data.get("type") == "interrupt":
                                    print(f"\n[INTERRUPT] Next step: {data['next']}")
                                    return data['next']
                                elif data.get("type") == "done":
                                    print("\n[DONE]")
                                elif data.get("type") == "status":
                                    print(f"\n[STATUS] {data['node']}")
                            except json.JSONDecodeError:
                                print(f"\nRaw data: {data_str}")
            else:
                print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")
    print("\n")

def test_chat_state(thread_id="test_thread_001"):
    print(f"Testing /chat/state for {thread_id}...")
    url = f"{BASE_URL}/chat/state"
    payload = {"thread_id": thread_id}
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")
    print("\n")

def test_chat_approve(thread_id="test_thread_001", approved=True):
    print(f"Testing /chat/approve for {thread_id} (approved={approved})...")
    url = f"{BASE_URL}/chat/approve"
    payload = {
        "thread_id": thread_id,
        "approved": approved
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            print(json.dumps(response.json(), indent=2, ensure_ascii=False))
        else:
            print(f"Error: {response.status_code} - {response.text}")
    except Exception as e:
        print(f"Request failed: {e}")
    print("\n")

if __name__ == "__main__":
    # 1. Start Chat Stream (should pause at human_review)
    next_step = test_chat_stream()
    
    # 2. Check State
    test_chat_state()
    
    # 3. Approve if paused
    if next_step: # It might be a list or string depending on graph state
        test_chat_approve()
