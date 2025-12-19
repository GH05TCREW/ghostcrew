"""Tests for the RAG knowledge system."""

import pytest
import numpy as np
from pathlib import Path
from unittest.mock import patch

from pentestagent.knowledge.rag import RAGEngine, Document


class TestDocument:
    """Tests for Document dataclass."""
    
    def test_create_document(self):
        """Test creating a document."""
        doc = Document(content="Test content", source="test.md")
        assert doc.content == "Test content"
        assert doc.source == "test.md"
        assert doc.metadata == {}
        assert doc.doc_id is not None
    
    def test_document_with_metadata(self):
        """Test document with metadata."""
        doc = Document(
            content="Test",
            source="test.md",
            metadata={"cve_id": "CVE-2021-1234", "severity": "high"}
        )
        assert doc.metadata["cve_id"] == "CVE-2021-1234"
        assert doc.metadata["severity"] == "high"
    
    def test_document_with_embedding(self):
        """Test document with embedding."""
        embedding = np.random.rand(384)
        doc = Document(content="Test", source="test.md", embedding=embedding)
        assert doc.embedding is not None
        assert len(doc.embedding) == 384
    
    def test_document_with_custom_id(self):
        """Test document with custom doc_id."""
        doc = Document(content="Test", source="test.md", doc_id="custom-id-123")
        assert doc.doc_id == "custom-id-123"


class TestRAGEngine:
    """Tests for RAGEngine class."""
    
    @pytest.fixture
    def rag_engine(self, tmp_path):
        """Create a RAG engine for testing."""
        return RAGEngine(
            knowledge_path=tmp_path / "knowledge",
            use_local_embeddings=True
        )
    
    def test_create_engine(self, rag_engine):
        """Test creating a RAG engine."""
        assert rag_engine is not None
        assert len(rag_engine.documents) == 0
        assert rag_engine.embeddings is None
    
    def test_get_document_count_empty(self, rag_engine):
        """Test document count on empty engine."""
        assert rag_engine.get_document_count() == 0
    
    def test_clear(self, rag_engine):
        """Test clearing the engine."""
        rag_engine.documents.append(Document(content="test", source="test.md"))
        rag_engine.embeddings = np.random.rand(1, 384)
        rag_engine._indexed = True
        
        rag_engine.clear()
        
        assert len(rag_engine.documents) == 0
        assert rag_engine.embeddings is None
        assert rag_engine._indexed == False


class TestRAGEngineChunking:
    """Tests for text chunking functionality."""
    
    @pytest.fixture
    def engine(self, tmp_path):
        """Create engine for chunking tests."""
        return RAGEngine(knowledge_path=tmp_path)
    
    def test_chunk_short_text(self, engine):
        """Test chunking text shorter than chunk size."""
        text = "This is a short paragraph.\n\nThis is another paragraph."
        chunks = engine._chunk_text(text, source="test.md", chunk_size=1000)
        
        assert len(chunks) >= 1
        assert all(isinstance(c, Document) for c in chunks)
    
    def test_chunk_preserves_source(self, engine):
        """Test that chunking preserves source information."""
        text = "Test paragraph 1.\n\nTest paragraph 2."
        chunks = engine._chunk_text(text, source="my_source.md")
        
        assert all(c.source == "my_source.md" for c in chunks)
