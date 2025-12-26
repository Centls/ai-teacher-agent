import requests
import json
import sseclient

def test_chat_api():
    url = "http://localhost:8001/api/chat"
    payload = {
        "message": "Hello, Nexus!",
        "session_id": "test_session"
    }
    headers = {"Content-Type": "application/json"}

    print(f"Connecting to {url}...")
    try:
        response = requests.post(url, json=payload, headers=headers, stream=True)
        response.raise_for_status()
        
        client = sseclient.SSEClient(response)
        for event in client.events():
            print(f"Event: {event.event}")
            print(f"Data: {event.data}")
            if event.event == "end":
                print("Stream ended.")
                break
                
    except Exception as e:
        print(f"API Test Failed: {e}")

if __name__ == "__main__":
    test_chat_api()
