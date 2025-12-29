import requests
import json
import uuid

def test_supervisor(question):
    url = "http://127.0.0.1:8002/chat/supervisor"
    thread_id = str(uuid.uuid4())
    payload = {"question": question, "thread_id": thread_id}
    
    with open("test_output.txt", "a", encoding="utf-8") as f:
        f.write(f"Testing Question: {question}\n")
        
        with requests.post(url, json=payload, stream=True) as r:
            if r.status_code != 200:
                f.write(f"Error: {r.status_code} - {r.text}\n")
                return
                
            for line in r.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8')
                    if decoded_line.startswith("data: "):
                        data_str = decoded_line[6:]
                        if data_str == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            f.write(f"Received: {json.dumps(data, ensure_ascii=False)}\n")
                        except:
                            f.write(f"Raw: {data_str}\n")
        f.write("\n" + "="*50 + "\n")

if __name__ == "__main__":
    # Clear file
    with open("test_output.txt", "w") as f:
        f.write("")
    test_supervisor("Hello, who are you?")
    test_supervisor("How can I improve my Facebook Ads ROI?")
