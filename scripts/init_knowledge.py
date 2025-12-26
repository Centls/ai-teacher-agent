"""
Knowledge Base Initialization Script
=====================================
This script initializes the knowledge base with standard project documents.
Run this after cloning the repository to set up the local knowledge store.

Usage:
    python scripts/init_knowledge.py

Dependencies:
    - ChromaKnowledgeProvider from src.services.rag.chroma_service
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.rag.chroma_service import ChromaKnowledgeProvider


# Standard documents to ingest (relative to project root)
# These are BUSINESS knowledge documents, NOT project development docs
STANDARD_DOCS = [
    # Business Knowledge
    "data/knowledge/tcm_watch_intro.md",
    "data/knowledge/tcm_wiki.txt",
    # Product Requirements (PRD) - used as constraints by Teachers
    "data/prd/marketing_prd.md",
    "data/prd/tcm_smartwatch_prd.md",
]


def main():
    """Initialize knowledge base with standard documents."""
    print("=" * 50)
    print("Knowledge Base Initialization")
    print("=" * 50)
    
    # Initialize the knowledge provider
    print("\n[1/2] Initializing ChromaDB...")
    try:
        provider = ChromaKnowledgeProvider()
        print("✓ ChromaDB initialized successfully")
    except Exception as e:
        print(f"✗ Failed to initialize ChromaDB: {e}")
        return 1
    
    # Ingest standard documents
    print("\n[2/2] Ingesting standard documents...")
    success_count = 0
    failed_count = 0
    
    for doc_path in STANDARD_DOCS:
        full_path = project_root / doc_path
        
        if not full_path.exists():
            print(f"  ⚠ Skipped (not found): {doc_path}")
            continue
            
        try:
            doc_id = provider.ingest_document(str(full_path))
            print(f"  ✓ Ingested: {doc_path} (ID: {doc_id[:8]}...)")
            success_count += 1
        except Exception as e:
            print(f"  ✗ Failed: {doc_path} - {e}")
            failed_count += 1
    
    # Summary
    print("\n" + "=" * 50)
    print(f"Initialization Complete!")
    print(f"  - Ingested: {success_count} documents")
    print(f"  - Failed:   {failed_count} documents")
    print("=" * 50)
    
    return 0 if failed_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
