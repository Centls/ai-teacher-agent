#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test Script for Semantic Chunking Integration

Features tested:
1. ChonkieSemanticSplitter loading with BAAI/bge-large-zh-v1.5
2. Semantic splitting behavior on sample text
3. Integration with RAGPipeline's Parent-Child Index
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
from src.services.rag.pipeline import RAGPipeline

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_semantic_splitter_direct():
    """Test ChonkieSemanticSplitter directly"""
    print("\n" + "="*60)
    print("1. Testing ChonkieSemanticSplitter (Direct)")
    print("="*60)

    try:
        from src.services.rag.semantic_splitter import ChonkieSemanticSplitter

        # Override settings for testing
        embedding_model = "BAAI/bge-large-zh-v1.5"
        print(f"Loading model: {embedding_model}")

        splitter = ChonkieSemanticSplitter(
            embedding_model=embedding_model,
            similarity_percentile=85.0,
            chunk_size=500,  # Small chunk size for testing
            min_sentences=1
        )

        # Test text (Marketing content about AI)
        test_text = """
        AI Marketing Nexus 是一个革命性的营销平台。它结合了生成式 AI 和数据分析技术，帮助企业实现营销自动化。

        我们的核心功能包括：
        1. 智能文案生成：基于大模型自动生成高质量营销文案。
        2. 客户画像分析：利用机器学习算法深入洞察客户需求。
        3. 多渠道投放：一键分发内容到各大社交媒体平台。

        关于价格方案：
        我们提供灵活的订阅模式。初创企业可以使用免费版，包含基础功能。
        成长型企业推荐专业版，解锁高级分析功能。
        大型企业可以定制企业版，获得专属支持和私有化部署。

        联系我们：
        如果您有任何问题，请发送邮件至 support@aimarketing.com。
        我们的团队将在24小时内回复。
        """

        doc = Document(page_content=test_text, metadata={"source": "test_doc"})

        print("\nSplitting document...")
        chunks = splitter.split_documents([doc])

        print(f"\nResult: {len(chunks)} chunks generated")
        for i, chunk in enumerate(chunks):
            print(f"\n--- Chunk {i+1} (Length: {len(chunk.page_content)}) ---")
            print(chunk.page_content.strip())
            print(f"Metadata: {chunk.metadata}")

        return True

    except ImportError as e:
        logger.error(f"Import failed: {e}")
        return False
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_rag_pipeline_integration():
    """Test integration with RAGPipeline"""
    print("\n" + "="*60)
    print("2. Testing RAGPipeline Integration")
    print("="*60)

    # Setup temporary test directory
    test_db_path = "./data/test_chroma_db_semantic"
    test_docstore_path = Path("./data/test_parent_docstore_semantic")

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
    settings.SEMANTIC_CHUNKING_ENABLED = True
    settings.SEMANTIC_EMBEDDING_MODEL = "BAAI/bge-large-zh-v1.5"
    settings.PARENT_CHILD_ENABLED = True

    try:
        # Initialize Pipeline
        print(f"Initializing RAGPipeline with SEMANTIC_CHUNKING_ENABLED={settings.SEMANTIC_CHUNKING_ENABLED}")
        pipeline = RAGPipeline(vector_db_path=test_db_path)

        # Verify parent_retriever is initialized correctly
        if pipeline.parent_retriever:
            print("✅ Parent-Child Index initialized")

            # Check internal splitter type (hacky inspection)
            splitter = pipeline.parent_retriever.parent_splitter
            print(f"Parent Splitter Type: {type(splitter)}")

            from src.services.rag.semantic_splitter import ChonkieSemanticSplitter
            if isinstance(splitter, ChonkieSemanticSplitter):
                print("✅ Confirmed: Using ChonkieSemanticSplitter")
            else:
                print(f"❌ Warning: Using {type(splitter)} instead of ChonkieSemanticSplitter")
        else:
            print("❌ Parent-Child Index failed to initialize")
            return False

        # Ingest text
        test_text = """
        # 产品介绍
        AI Teacher Nexus 是一个智能教育辅助系统。它通过多模态 RAG 技术，帮助教师快速生成教案和回答学生问题。

        ## 核心技术
        系统采用了最先进的父子索引技术。
        父子索引解决了检索粒度和上下文完整性的矛盾。
        通过检索小块（Child Chunks）来定位信息，然后返回对应的大块（Parent Chunks）给 LLM。

        ## 语义分块
        我们引入了 Chonkie 库进行语义分块。
        语义分块基于 embedding 相似度，自动识别文本中的语义转折点。
        这比传统的固定字符数分块更符合人类的阅读逻辑。
        """

        print("\nIngesting text...")
        pipeline.ingest_text(test_text, metadata={"title": "Test Semantic Chunking"})

        # Retrieve
        query = "什么是父子索引？"
        print(f"\nRetrieving for query: '{query}'")
        results = pipeline.retrieve(query, k=1)

        if results:
            print(f"\n✅ Retrieved {len(results)} document")
            print(f"Content: {results[0].page_content[:100]}...")
            print(f"Metadata: {results[0].metadata}")
        else:
            print("❌ No results found")

        # Explicitly close client/persist to release locks if possible (Chroma < 0.4.x)
        # For newer Chroma, just dereference
        pipeline = None

        return True

    except Exception as e:
        logger.error(f"Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        safe_cleanup()

if __name__ == "__main__":
    success_1 = test_semantic_splitter_direct()
    if success_1:
        test_rag_pipeline_integration()
