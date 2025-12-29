import asyncio
from src.services.rag.vector import VectorKnowledgeProvider

async def test_chroma_rag():
    print("--- Testing Chroma RAG Integration (Adapted Pipeline) ---")
    try:
        # Initialize Provider
        provider = VectorKnowledgeProvider()
        print("[OK] Provider initialized successfully")
        
        # Test Ingestion
        test_text = "AI Teacher Nexus uses a modular RAG pipeline adapted from Local_Chat_RAG."
        print(f"Ingesting text: '{test_text}'")
        provider.ingest_text(test_text, source="test_script", namespace="test_ns")
        
        # Test Query
        query = "What RAG pipeline does AI Teacher Nexus use?"
        print(f"Querying: '{query}'")
        result = provider.query(query, namespace="test_ns")
        print(f"Result: {result}")
        
        if "Local_Chat_RAG" in result:
            print("[OK] Retrieval successful!")
        else:
            print("[FAIL] Retrieval failed or content mismatch.")
            
    except Exception as e:
        print(f"[ERROR] Error: {e}")
        with open("api_error.txt", "w", encoding="utf-8") as f:
            f.write(str(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_chroma_rag())
