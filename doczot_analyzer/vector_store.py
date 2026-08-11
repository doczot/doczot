"""Vector store implementation for semantic search.

This module handles embedding generation and similarity search.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple
import numpy as np
from doczot_analyzer.models import DocChunk

class VectorStore(ABC):
    """Abstract base class for vector storage and retrieval."""
    
    @abstractmethod
    def add_chunks(self, chunks: List[DocChunk]):
        """Add documentation chunks to the store."""
        pass
        
    @abstractmethod
    def search(self, query: str, limit: int = 3) -> List[Tuple[DocChunk, float]]:
        """Search for similar chunks.
        
        Returns:
            List of (chunk, score) tuples.
        """
        pass

class LocalVectorStore(VectorStore):
    """In-memory vector store using sentence-transformers and numpy."""
    
    def __init__(self, model_name: str = "all-mpnet-base-v2"):
        self.model_name = model_name
        self._model = None
        self.chunks: List[DocChunk] = []
        self.embeddings: List[np.ndarray] = []

    @property
    def model(self):
        """Load the embedding model on first use.

        Lazy (including the sentence_transformers/torch import, which
        alone takes several seconds) so commands that never embed
        anything - cached sessions, doc-less repos - don't pay for it.
        """
        if self._model is None:
            from sentence_transformers import SentenceTransformer

            print(f"Loading model: {self.model_name}")
            self._model = SentenceTransformer(self.model_name)
        return self._model


    def add_chunks(self, chunks: List[DocChunk]):
        """Add chunks and generate embeddings."""
        if not chunks:
            return
            
        new_texts = [
            f"{c.section_header}: {c.content}" if c.section_header else c.content 
            for c in chunks
        ]
        
        new_embeddings = self.model.encode(new_texts)
        
        self.chunks.extend(chunks)
        if len(self.embeddings) == 0:
            self.embeddings = new_embeddings
        else:
            self.embeddings = np.vstack([self.embeddings, new_embeddings])
            
    def search(self, query: str, limit: int = 3) -> List[Tuple[DocChunk, float]]:
        """Cosine similarity search."""
        if not self.chunks:
            return []
            
        query_embedding = self.model.encode([query])[0]
        
        # Calculate cosine similarity
        # sim = (a . b) / (|a| * |b|)
        scores = np.dot(self.embeddings, query_embedding) / (
            np.linalg.norm(self.embeddings, axis=1) * np.linalg.norm(query_embedding)
        )
        
        # Get top k indices
        top_k_indices = np.argsort(scores)[::-1][:limit]
        
        results = []
        for idx in top_k_indices:
            results.append((self.chunks[idx], float(scores[idx])))
            
        return results
