import sys
import os

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.services.rag.pipeline import RAGPipeline

def list_docs():
    pipeline = RAGPipeline()
    data = pipeline.vectorstore.get()
    metadatas = data['metadatas']
    
    if not metadatas:
        print("ChromaDB is empty.")
        return []

    # Aggregate by source_file
    docs = {}
    for m in metadatas:
        if not m: continue
        src = m.get('source_file', 'unknown')
        if src not in docs:
            docs[src] = {
                'original_filename': m.get('original_filename', 'unknown'),
                'count': 0,
                'type': m.get('type', 'unknown')
            }
        docs[src]['count'] += 1

    sorted_docs = sorted(docs.items())
    
    print("\n--- DOC LIST ---")
    for idx, (src, info) in enumerate(sorted_docs):
        # Print simple format: Index | Filename | Path
        print(f"{idx} | {info['original_filename']} | {src}")
    print("--- END LIST ---\n")
    return sorted_docs

def delete_doc(target):
    # Try to parse as index
    docs = list_docs()
    source_file_to_delete = None
    
    try:
        idx = int(target)
        if 0 <= idx < len(docs):
            source_file_to_delete = docs[idx][0]
            print(f"\nSelected document by index {idx}: {source_file_to_delete}")
    except ValueError:
        # Treat as path string
        source_file_to_delete = target

    if not source_file_to_delete:
        print("Invalid target or index out of range.")
        return

    pipeline = RAGPipeline()
    print(f"Deleting documents with source_file: {repr(source_file_to_delete)}")
    
    # Debug: Check if we can find it manually
    data = pipeline.vectorstore.get(where={"source_file": source_file_to_delete})
    ids = data['ids']
    print(f"DEBUG: Found {len(ids)} IDs to delete: {ids[:5]}...")
    
    success = pipeline.delete_document(source_file_to_delete)
    if success:
        print("Deletion successful.")
        print("\nVerifying deletion...")
        list_docs()
    else:
        print("Deletion failed.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/rag_manager.py [list|delete <index_or_path>]")
    elif sys.argv[1] == "list":
        list_docs()
    elif sys.argv[1] == "delete":
        if len(sys.argv) < 3:
            print("Usage: python scripts/rag_manager.py delete <index_or_path>")
        else:
            delete_doc(sys.argv[2])
