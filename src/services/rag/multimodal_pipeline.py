# -*- coding: utf-8 -*-
"""
Multimodal RAG Pipeline

Extends RAGPipeline with multimodal file processing capability.
All processing is delegated to Docling service (which handles docs, images, and audio).

External Dependencies:
    - Docling Service (unified document/OCR/ASR)
    - LangChain (fallback for text formats)
"""

import os
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

from langchain_core.documents import Document

from .pipeline import RAGPipeline
from src.services.multimodal.sync_client import MultimodalSyncClient, ProcessResult

logger = logging.getLogger(__name__)


class MultimodalRAGPipeline(RAGPipeline):
    """
    Multimodal RAG Pipeline

    Extends RAGPipeline with support for documents, images, and audio via Docling service.

    Usage:
        pipeline = MultimodalRAGPipeline()
        pipeline.ingest("data/doc.pdf")      # PDF via Docling (fallback to LangChain)
        pipeline.ingest("data/image.png")    # Image OCR via Docling
        pipeline.ingest("data/audio.mp3")    # Audio ASR via Docling (Whisper)
    """

    # Formats handled by Docling service
    DOCLING_FORMATS = {
        # Documents
        ".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt",
        ".html", ".htm", ".md", ".markdown",
        # Images
        ".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif",
        # Audio (via Whisper integration in Docling service)
        ".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"
    }

    # Text formats handled by parent class (LangChain)
    TEXT_FORMATS = {".txt", ".csv"}

    def __init__(self, vector_db_path: str = "./chroma_db", chunking_strategy: str = "auto"):
        """
        Initialize Multimodal RAG Pipeline

        Args:
            vector_db_path: ChromaDB persistence path
            chunking_strategy: Chunking strategy
        """
        super().__init__(vector_db_path, chunking_strategy)
        self._multimodal_client: Optional[MultimodalSyncClient] = None
        logger.info("Initialized MultimodalRAGPipeline (Docling-based)")

    @property
    def multimodal_client(self) -> MultimodalSyncClient:
        """Lazy-load multimodal client"""
        if self._multimodal_client is None:
            self._multimodal_client = MultimodalSyncClient()
        return self._multimodal_client

    def is_multimodal_file(self, file_path: str) -> bool:
        """Check if file should be processed by Docling"""
        ext = os.path.splitext(file_path)[-1].lower()
        return ext in self.DOCLING_FORMATS

    def load_document(self, file_path: str) -> List[Document]:
        """
        Load document (auto-select processor)

        Processing priority:
        1. Docling formats (PDF/DOCX/images/audio) -> Docling service
        2. Fallback: If Docling fails, try standard LangChain loaders for PDF/DOCX
        3. Text formats (TXT/CSV) -> Parent class (LangChain)

        Args:
            file_path: File path

        Returns:
            List[Document]: Document list
        """
        ext = os.path.splitext(file_path)[-1].lower()

        # Text formats: use parent class directly
        if ext in self.TEXT_FORMATS:
            return super().load_document(file_path)

        # Docling formats: call Docling service with fallback
        if ext in self.DOCLING_FORMATS:
            try:
                return self._load_via_docling(file_path)
            except Exception as e:
                # Fallback to parent for some document formats (PDF, DOCX)
                # Parent class uses PyPDFLoader, UnstructuredWordDocumentLoader, etc.
                if ext in {".pdf", ".docx", ".doc", ".xlsx", ".csv", ".txt", ".md"}:
                    logger.warning(f"Docling failed for {file_path}: {e}. Fallback to LangChain loader.")
                    return super().load_document(file_path)

                # For images/audio, no standard fallback exists in parent, so re-raise
                logger.error(f"Docling processing failed for {file_path} and no fallback available: {e}")
                raise

        # Other formats: try parent class
        return super().load_document(file_path)

    def _load_via_docling(self, file_path: str) -> List[Document]:
        """
        Load file via Docling service.

        All processing logic is in Docling service (server-side).
        This method only handles HTTP call orchestration.
        """
        file_name = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[-1].lower()

        logger.info(f"Processing via Docling service: {file_name}")

        # Call Docling service
        result: ProcessResult = self.multimodal_client.process_file(file_path)

        if not result.success:
            raise ValueError(f"Docling service returned error: {result.error}")

        if not result.text.strip():
            logger.warning(f"No text extracted from {file_name}")
            return []

        # Build Document object
        doc = Document(
            page_content=result.text,
            metadata={
                "source": file_path,
                "file_name": file_name,
                "file_type": ext,
                "processing_source": "docling_service",
                **result.metadata
            }
        )

        logger.info(f"Extracted {len(result.text)} chars from {file_name}")
        return [doc]

    def ingest(self, file_path: str, metadata: dict = None):
        """
        Ingest file to vector database (multimodal support)

        Args:
            file_path: File path
            metadata: Additional metadata
        """
        # Unified loading logic with fallback support
        try:
            docs = self.load_document(file_path)
        except Exception as e:
            logger.error(f"Failed to load document {file_path}: {e}")
            return

        if not docs:
            logger.warning(f"No content extracted from {file_path}, skipping")
            return

        # Chunk documents
        # For Docling results (often markdown), we might want smarter chunking,
        # but for consistency we use the same strategy as parent or simple recursive.

        # Check if we should use parent's strategy logic
        splitter = self._get_text_splitter(docs, file_path)

        # MarkdownHeaderTextSplitter expects string, not documents
        from langchain_text_splitters import MarkdownHeaderTextSplitter
        if isinstance(splitter, MarkdownHeaderTextSplitter):
            text = "\n\n".join([d.page_content for d in docs])
            splits = splitter.split_text(text)
        else:
            splits = splitter.split_documents(docs)

        # Attach file-level metadata
        for doc in splits:
            doc.metadata = doc.metadata or {}
            if metadata:
                doc.metadata.update(metadata)
            doc.metadata['source_file'] = file_path

            # Preserve processing source if present (e.g. from Docling)
            if docs and 'processing_source' in docs[0].metadata:
                doc.metadata['processing_source'] = docs[0].metadata['processing_source']

        self.vectorstore.add_documents(splits)
        logger.info(f"Ingested {len(splits)} chunks from {file_path}")

    def get_supported_formats(self) -> Dict[str, List[str]]:
        """Get all supported file formats"""
        return {
            "document": [".pdf", ".docx", ".doc", ".xlsx", ".xls", ".pptx", ".ppt", ".txt", ".csv", ".html", ".md"],
            "image": [".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff", ".tif"],
            "audio": [".mp3", ".wav", ".m4a", ".flac", ".ogg", ".wma"]
        }
