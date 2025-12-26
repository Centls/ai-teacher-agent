import requests
import json
import sseclient

def test_chat_api_v2():
    url = "http://localhost:8001/api/chat"
    
    # New Payload Format
    payload = {
        "messages": [
            {"role": "user", "content": "Hello, I need help with marketing."}
        ],
        "session_id": "test_session_v2",
        "teacher_id": "marketing"
    }
    
    print(f"Testing API at {url} with payload: {json.dumps(payload, indent=2)}")
    
    try:
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()
        
        client = sseclient.SSEClient(response)
        
        print("--- Streaming Response ---")
        for event in client.events():
            print(f"Event: {event.event}")
            print(f"Data: {event.data}")
            
            if event.event == "message":
                data = json.loads(event.data)
                print(f"Content: {data.get('content')}")
            
            if event.event == "end":
                print("--- Stream Ended ---")
                break
                
    except Exception as e:
        print(f"API Test Failed: {e}")

if __name__ == "__main__":
    test_chat_api_v2()
