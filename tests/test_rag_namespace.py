import sys
import os

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from src.services.rag.vector import VectorKnowledgeProvider

def test_namespace_isolation():
    print("--- Testing Namespace Isolation ---")
    
    # Initialize Provider
    kp = VectorKnowledgeProvider(collection_name="test_namespace_isolation")
    
    # Clear existing data (if possible, or just use unique content)
    # Chroma doesn't have a clean "delete collection" in this simple wrapper, 
    # so we'll use unique content.
    
    unique_id = str(os.urandom(4).hex())
    content_a = f"Top Secret Plan Alpha {unique_id}: Launch at dawn."
    content_b = f"Top Secret Plan Beta {unique_id}: Launch at dusk."
    
    # Ingest with namespaces
    print(f"Ingesting Doc A into namespace 'user_1'...")
    kp.ingest_text(content_a, source="test", namespace="user_1")
    
    print(f"Ingesting Doc B into namespace 'user_2'...")
    kp.ingest_text(content_b, source="test", namespace="user_2")
    
    # Query Namespace 1
    print("\nQuerying 'Launch' in 'user_1'...")
    result_1 = kp.query("Launch", namespace="user_1")
    print(f"Result 1: {result_1}")
    
    if content_a in result_1 and content_b not in result_1:
        print("✅ PASS: User 1 only saw Plan Alpha.")
    else:
        print("❌ FAIL: User 1 saw wrong data.")
        
    # Query Namespace 2
    print("\nQuerying 'Launch' in 'user_2'...")
    result_2 = kp.query("Launch", namespace="user_2")
    print(f"Result 2: {result_2}")
    
    if content_b in result_2 and content_a not in result_2:
        print("✅ PASS: User 2 only saw Plan Beta.")
    else:
        print("❌ FAIL: User 2 saw wrong data.")

if __name__ == "__main__":
    test_namespace_isolation()
