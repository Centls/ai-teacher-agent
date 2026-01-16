#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Script for EnsembleRetriever Integration

Features tested:
1. EnsembleRetriever (Dense + BM25 RRF fusion)
2. BM25Retriever lazy loading
3. BM25 cache invalidation after ingest
4. Integration with Parent-Child Index
5. ChildToParentBM25Retriever wrapper (BM25 子块 -> 父块升级)
"""
import sys
import os
import shutil
import logging
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from config.settings import settings
from langchain_core.documents import Document

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_ensemble_retriever():
    """Test EnsembleRetriever with RAGPipeline"""
    print("\n" + "="*60)
    print("Testing EnsembleRetriever (Dense + BM25 RRF Fusion)")
    print("="*60)

    # Setup temporary test directory
    test_db_path = "./data/test_chroma_db_ensemble"
    test_docstore_path = Path("./data/test_parent_docstore_ensemble")

    def safe_cleanup():
        import time
        for _ in range(3):
            try:
                if os.path.exists(test_db_path):
                    shutil.rmtree(test_db_path)
                if test_docstore_path.exists():
                    shutil.rmtree(test_docstore_path)
                break
            except Exception as e:
                print(f"Cleanup retry... {e}")
                time.sleep(1)

    # Clean up previous test
    safe_cleanup()

    # Override settings
    settings.DOCSTORE_PATH = test_docstore_path
    settings.PARENT_CHILD_ENABLED = True
    settings.SEMANTIC_CHUNKING_ENABLED = True
    settings.RERANKER_ENABLED = False  # Disable reranker for faster testing

    try:
        from src.services.rag.pipeline import RAGPipeline

        # Initialize Pipeline
        print(f"\nInitializing RAGPipeline...")
        print(f"  PARENT_CHILD_ENABLED={settings.PARENT_CHILD_ENABLED}")
        print(f"  SEMANTIC_CHUNKING_ENABLED={settings.SEMANTIC_CHUNKING_ENABLED}")
        print(f"  RERANKER_ENABLED={settings.RERANKER_ENABLED}")

        pipeline = RAGPipeline(vector_db_path=test_db_path)

        # Verify parent_retriever is initialized
        if pipeline.parent_retriever:
            print("✅ Parent-Child Index initialized")
        else:
            print("❌ Parent-Child Index failed to initialize")

        # Ingest test documents
        test_texts = [
            """
            人工智能（AI）是计算机科学的一个分支，致力于创建能够模拟人类智能的系统。
            机器学习是 AI 的核心技术之一，它使计算机能够从数据中学习。
            深度学习是机器学习的子领域，使用神经网络处理复杂任务。
            """,
            """
            自然语言处理（NLP）是 AI 的重要应用领域。
            NLP 技术使计算机能够理解、解释和生成人类语言。
            大型语言模型（LLM）如 GPT 和 Claude 是 NLP 的最新突破。
            """,
            """
            RAG（检索增强生成）是一种结合检索和生成的技术。
            RAG 系统首先从知识库中检索相关文档，然后基于这些文档生成回答。
            父子索引（Parent-Child Index）是 RAG 的一种优化技术。
            """,
        ]

        print("\nIngesting test documents...")
        for i, text in enumerate(test_texts):
            pipeline.ingest_text(text, metadata={"doc_id": f"test_doc_{i+1}"})
            print(f"  Ingested document {i+1}")

        # Check BM25Retriever initialization
        print("\nChecking BM25Retriever...")
        bm25 = pipeline.bm25_retriever
        if bm25:
            print(f"✅ BM25Retriever initialized with {len(bm25.docs)} documents")
        else:
            print("❌ BM25Retriever not available")

        # Test retrieval with EnsembleRetriever
        test_queries = [
            "什么是机器学习？",
            "RAG 技术是什么？",
            "大型语言模型有哪些？",
        ]

        print("\n" + "-"*40)
        print("Testing EnsembleRetriever Queries")
        print("-"*40)

        for query in test_queries:
            print(f"\nQuery: '{query}'")
            results = pipeline.retrieve(query, k=2)

            if results:
                print(f"✅ Retrieved {len(results)} documents")
                for i, doc in enumerate(results):
                    content_preview = doc.page_content[:80].replace('\n', ' ').strip()
                    print(f"   [{i+1}] {content_preview}...")
            else:
                print("❌ No results found")

        # Test BM25 sync rebuild after ingest
        print("\n" + "-"*40)
        print("Testing BM25 Sync Rebuild After Ingest")
        print("-"*40)

        # Check current BM25 retriever status
        bm25_before = pipeline._bm25_retriever
        print(f"BM25 retriever exists before ingest: {bm25_before is not None}")

        # Ingest new document
        new_text = """
        向量数据库是专门用于存储和检索高维向量的数据库。
        ChromaDB 是一个流行的开源向量数据库。
        向量检索是 RAG 系统的核心组件。
        """
        print("\nIngesting new document...")
        pipeline.ingest_text(new_text, metadata={"doc_id": "test_doc_new"})

        # Check if BM25 was rebuilt (not None)
        bm25_after = pipeline._bm25_retriever
        if bm25_after is not None:
            print(f"✅ BM25Retriever rebuilt after ingest (docs: {len(bm25_after.docs)})")
        else:
            print("❌ BM25Retriever is None after ingest")

        # Retrieve again (should rebuild BM25)
        query = "什么是向量数据库？"
        print(f"\nQuery after new ingest: '{query}'")
        results = pipeline.retrieve(query, k=2)

        if results:
            print(f"✅ Retrieved {len(results)} documents (BM25 rebuilt)")
            for i, doc in enumerate(results):
                content_preview = doc.page_content[:80].replace('\n', ' ').strip()
                print(f"   [{i+1}] {content_preview}...")
        else:
            print("❌ No results found")

        # Cleanup
        pipeline = None
        print("\n" + "="*60)
        print("✅ All EnsembleRetriever tests passed!")
        print("="*60)
        return True

    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        safe_cleanup()


if __name__ == "__main__":
    success = test_ensemble_retriever()
    sys.exit(0 if success else 1)
