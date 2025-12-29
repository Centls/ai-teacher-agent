import requests
import json
import time

BASE_URL = "http://127.0.0.1:8002"

def create_thread():
    res = requests.post(f"{BASE_URL}/threads", json={"title": "Learning Test"})
    return res.json()["id"]

def send_message(thread_id, question):
    print(f"\nSending: {question}")
    res = requests.post(f"{BASE_URL}/chat/stream", json={"thread_id": thread_id, "question": question}, stream=True)
    
    content = ""
    interrupt_next = None
    
    for line in res.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith("data: "):
                data = json.loads(line[6:])
                if data["type"] == "token":
                    content += data["content"]
                    print(data["content"], end="", flush=True)
                elif data["type"] == "interrupt":
                    interrupt_next = data["next"]
                    print(f"\n[Interrupted] Next: {interrupt_next}")
                elif data["type"] == "error":
                    print(f"\n[Error] {data['message']}")
    
    print("\n")
    return content, interrupt_next

def approve(thread_id, approved=True, feedback=None):
    data = {"thread_id": thread_id, "approved": approved}
    if feedback:
        data["feedback"] = feedback
    print(f"\nApproving with feedback: {feedback}")
    res = requests.post(f"{BASE_URL}/chat/approve", json=data)
    print(f"Approve Res: {res.json()}")

if __name__ == "__main__":
    print("Starting Learning Test...")
    thread_id = create_thread()
    print(f"Thread ID: {thread_id}")
    
    # 1. First Turn
    send_message(thread_id, "How to market coffee?")
    
    # 2. Approve with Feedback (Simulate Learning)
    # Note: Currently learning happens at START of next turn.
    # So we approve this one (maybe with feedback that triggers retry? No, let's just approve)
    # Wait, if I want to learn "Use emojis", I should say it now.
    # But my graph learns at START.
    # So this feedback won't be reflected until NEXT turn.
    approve(thread_id, approved=True, feedback="approved")
    
    # 3. Second Turn (Should use learned rules? No, we haven't learned yet because learning runs at start)
    # Wait, learning runs at start of THIS turn.
    # Turn 1: Learning (No history) -> Retrieve -> ... -> Generate -> End.
    # Turn 2: Learning (History from Turn 1) -> Retrieve ...
    
    # So if I want to teach it "Use emojis", I should do it in Turn 2 input?
    # Or if I rejected Turn 1 with "Use emojis", then it would retry.
    # But I approved Turn 1.
    
    # Let's try:
    # Turn 1: "How to market coffee?" -> Output (No emojis).
    # User: "That's good, but please use emojis next time."
    # Turn 2: "Okay, noted." (Learning runs, sees "Use emojis")
    # Turn 3: "How to market tea?" -> Output (With emojis).
    
    print("\n--- Sending Feedback ---")
    send_message(thread_id, "Please use emojis in your answers.")
    
    print("\n--- Testing Learning ---")
    send_message(thread_id, "How to market tea?")
