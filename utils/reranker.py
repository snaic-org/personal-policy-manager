# utils/reranker.py

"""
Cross-Encoder Reranking
Implements semantic reranking using pre-trained cross-encoder models.
"""

from typing import List, Dict, Any, Optional
from sentence_transformers import CrossEncoder


class CrossEncoderReranker:
    """
    Semantic reranking using Cross-Encoder models.
    
    Cross-encoders compute relevance scores by encoding query-document pairs
    together, providing more accurate relevance scores than bi-encoders but
    at higher computational cost.
    """
    
    def __init__(
        self,
        model_name: str = "cross-encoder/ms-marco-MiniLM-L-6-v2",
        device: str = "cpu",
        batch_size: int = 16,
        max_length: int = 512
    ):
        """
        Initialize cross-encoder model for reranking.
        
        Args:
            model_name: Hugging Face model identifier
                Recommended options:
                - cross-encoder/ms-marco-TinyBERT-L-2-v2 (fast, 17MB)
                - cross-encoder/ms-marco-MiniLM-L-6-v2 (balanced, 90MB) - DEFAULT
                - cross-encoder/ms-marco-MiniLM-L-12-v2 (accurate, 120MB)
                - cross-encoder/qnli-distilroberta-base (most accurate, 420MB)
            device: "cpu" or "cuda"
            batch_size: Batch size for encoding (higher = faster but more memory)
            max_length: Maximum token length for input sequences
        """
        print(f"[CrossEncoderReranker] Loading model: {model_name}")
        self.model = CrossEncoder(model_name, max_length=max_length, device=device)
        self.batch_size = batch_size
        self.model_name = model_name
        self.device = device
        print(f"[CrossEncoderReranker] Model loaded on {device}")
    
    def rerank(
        self,
        query: str,
        candidates: List[Dict[str, Any]],
        top_k: Optional[int] = None,
        score_field: str = "rerank_score"
    ) -> List[Dict[str, Any]]:
        """
        Rerank candidates using cross-encoder semantic similarity.
        
        Args:
            query: Original search query
            candidates: List of candidate documents
                Each dict must have 'content' field
            top_k: Number of top results to return (None = return all)
            score_field: Name for the new score field to add
        
        Returns:
            Reranked candidates sorted by cross-encoder score (highest first)
            Original candidates are modified in-place with new score field
        """
        if not candidates:
            return []
        
        # Prepare query-document pairs
        pairs = []
        valid_candidates = []
        
        for candidate in candidates:
            content = candidate.get("content", "")
            if content:
                pairs.append([query, content])
                valid_candidates.append(candidate)
        
        if not pairs:
            print("[CrossEncoderReranker] Warning: No valid candidates with content")
            return []
        
        # Score all pairs in batches
        print(f"[CrossEncoderReranker] Reranking {len(pairs)} candidates...")
        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False
        )
        
        # Add scores to original candidates
        for idx, candidate in enumerate(valid_candidates):
            candidate[score_field] = float(scores[idx])
        
        # Sort by cross-encoder score descending
        valid_candidates.sort(key=lambda x: x[score_field], reverse=True)
        
        # Return top_k if specified
        if top_k is not None:
            return valid_candidates[:top_k]
        
        return valid_candidates
    
    def rank(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None,
        return_scores: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Rank a list of document strings (simpler interface).
        
        Args:
            query: Search query
            documents: List of document strings
            top_k: Number of top results to return
            return_scores: Whether to include scores in output
        
        Returns:
            List of dicts with keys: 'text', 'score' (if return_scores=True), 'rank'
        """
        if not documents:
            return []
        
        # Prepare pairs
        pairs = [[query, doc] for doc in documents]
        
        # Score
        scores = self.model.predict(
            pairs,
            batch_size=self.batch_size,
            show_progress_bar=False
        )
        
        # Create result list with scores
        results = []
        for idx, (doc, score) in enumerate(zip(documents, scores)):
            result = {
                "text": doc,
                "rank": idx
            }
            if return_scores:
                result["score"] = float(score)
            results.append(result)
        
        # Sort by score descending
        results.sort(key=lambda x: x.get("score", 0), reverse=True)
        
        # Update ranks after sorting
        for idx, result in enumerate(results):
            result["rank"] = idx
        
        # Return top_k if specified
        if top_k is not None:
            return results[:top_k]
        
        return results
    
    def get_model_info(self) -> Dict[str, str]:
        """Return information about the loaded model."""
        return {
            "model_name": self.model_name,
            "device": self.device,
            "batch_size": self.batch_size,
            "max_length": self.model.max_length
        }
