"""Matching engine for DocZot.

Implements the 3-tier matching logic:
1. Exact Pattern Match
2. Vector Semantic Match
3. LLM Verification (Placeholder)
"""
from typing import List, Optional
from doczot_analyzer.models import Endpoint, DocReference, DocChunk, AnalysisReport
from doczot_analyzer.vector_store import VectorStore

class Matcher:
    def __init__(self, vector_store: Optional[VectorStore] = None):
        self.vector_store = vector_store
        
    def analyze(
        self, 
        endpoints: List[Endpoint], 
        doc_references: List[DocReference],
        doc_chunks: List[DocChunk] = None
    ) -> AnalysisReport:
        """Run full analysis on endpoints."""
        
        # Populate vector store if provided
        if self.vector_store and doc_chunks:
            self.vector_store.add_chunks(doc_chunks)
            
        for endpoint in endpoints:
            # Tier 1: Exact Match
            if self._check_exact_match(endpoint, doc_references):
                endpoint.is_documented = True
                endpoint.analysis_method = "exact"
                endpoint.confidence_score = 1.0
                continue
                
            # Tier 2: Vector Match
            if self.vector_store and endpoint.semantic_signature:
                match, score = self._check_vector_match(endpoint)
                if match:
                    endpoint.is_documented = True
                    endpoint.analysis_method = "vector"
                    endpoint.confidence_score = score
                    continue
                    
            # Tier 3: LLM Match (Placeholder)
            # In a real implementation, we would call the LLM here if score is ambiguous
            pass
            
            pass
            
        return AnalysisReport(
            endpoints=endpoints,
            total_endpoints=len(endpoints)
        )
        
    def _check_exact_match(self, endpoint: Endpoint, references: List[DocReference]) -> bool:
        """Check for exact method/path matches in references."""
        for ref in references:
            if ref.matches_endpoint(endpoint):
                return True
        return False
        
    def _check_vector_match(self, endpoint: Endpoint) -> (bool, float):
        """Check for semantic match using vector store."""
        if not self.vector_store:
            return False, 0.0
            
        results = self.vector_store.search(endpoint.semantic_signature, limit=1)
        if not results:
            return False, 0.0
            
        best_chunk, score = results[0]
        
        # Thresholds (to be tuned via Golden Dataset)
        HIGH_CONFIDENCE_THRESHOLD = 0.55
        
        if score >= HIGH_CONFIDENCE_THRESHOLD:
            return True, score
            
        return False, score
