# utils/fusion.py

"""
Reciprocal Rank Fusion (RRF)
Implements RRF algorithm for combining multiple ranked result lists.
"""

from typing import List, Dict, Any


def reciprocal_rank_fusion(
    faiss_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    k: int = 60,
    top_k: int = 10
) -> List[Dict[str, Any]]:
    """
    Combine two ranked lists using Reciprocal Rank Fusion.
    
    RRF Formula: RRF_score(doc) = sum(1 / (k + rank_i)) for all rankings where doc appears
    
    This method is more robust than weighted sum fusion and doesn't require
    score normalization. It handles cases where a document appears in only one
    ranking list or both.
    
    Args:
        faiss_results: Ranked results from FAISS semantic search
            Each dict must have: 'content', 'rank', 'metadata', etc.
        bm25_results: Ranked results from BM25 keyword search
            Each dict must have: 'content', 'rank', 'metadata', etc.
        k: RRF constant (default 60, recommended range: 10-100)
            Lower k = more weight to top-ranked items
            Higher k = more democratic fusion
        top_k: Number of final results to return
    
    Returns:
        List of combined results sorted by RRF score, with 'rrf_score' field added
    """
    # Index results by content for efficient lookup
    content_to_doc: Dict[str, Dict[str, Any]] = {}
    rrf_scores: Dict[str, float] = {}
    
    # Process FAISS results
    for result in faiss_results:
        content = result.get("content", "")
        if not content:
            continue
        
        # Store the full document (use first occurrence)
        if content not in content_to_doc:
            content_to_doc[content] = result.copy()
            rrf_scores[content] = 0.0
        
        # Add RRF contribution from FAISS ranking
        rank = result.get("rank", 0)
        rrf_scores[content] += 1.0 / (k + rank)
    
    # Process BM25 results
    for result in bm25_results:
        content = result.get("content", "")
        if not content:
            continue
        
        # Store the full document (use first occurrence)
        if content not in content_to_doc:
            content_to_doc[content] = result.copy()
            rrf_scores[content] = 0.0
        
        # Add RRF contribution from BM25 ranking
        rank = result.get("rank", 0)
        rrf_scores[content] += 1.0 / (k + rank)
    
    # Build final result list with RRF scores
    combined_results = []
    for content, doc in content_to_doc.items():
        doc["rrf_score"] = rrf_scores[content]
        combined_results.append(doc)
    
    # Sort by RRF score descending
    combined_results.sort(key=lambda x: x["rrf_score"], reverse=True)
    
    return combined_results[:top_k]


def reciprocal_rank_fusion_multi(
    ranked_lists: List[List[Dict[str, Any]]],
    k: int = 60,
    top_k: int = 10,
    list_names: List[str] = None
) -> List[Dict[str, Any]]:
    """
    Combine multiple ranked lists using Reciprocal Rank Fusion.
    
    This is a generalized version that can handle more than 2 ranking sources.
    Useful for scenarios with multiple retrieval methods (e.g., FAISS + BM25 + TF-IDF).
    
    Args:
        ranked_lists: List of ranked result lists
        k: RRF constant (default 60)
        top_k: Number of final results to return
        list_names: Optional names for each list (for debugging/tracking)
    
    Returns:
        List of combined results sorted by RRF score
    """
    if not ranked_lists:
        return []
    
    if list_names is None:
        list_names = [f"list_{i}" for i in range(len(ranked_lists))]
    
    # Index results by content
    content_to_doc: Dict[str, Dict[str, Any]] = {}
    rrf_scores: Dict[str, float] = {}
    
    # Process each ranked list
    for list_idx, ranked_list in enumerate(ranked_lists):
        list_name = list_names[list_idx] if list_idx < len(list_names) else f"list_{list_idx}"
        
        for result in ranked_list:
            content = result.get("content", "")
            if not content:
                continue
            
            # Store the full document (use first occurrence)
            if content not in content_to_doc:
                content_to_doc[content] = result.copy()
                rrf_scores[content] = 0.0
                # Track which lists this document appeared in
                content_to_doc[content]["rrf_source_lists"] = []
            
            # Add RRF contribution
            rank = result.get("rank", 0)
            rrf_scores[content] += 1.0 / (k + rank)
            
            # Track source
            content_to_doc[content]["rrf_source_lists"].append(list_name)
    
    # Build final result list with RRF scores
    combined_results = []
    for content, doc in content_to_doc.items():
        doc["rrf_score"] = rrf_scores[content]
        combined_results.append(doc)
    
    # Sort by RRF score descending
    combined_results.sort(key=lambda x: x["rrf_score"], reverse=True)
    
    return combined_results[:top_k]
