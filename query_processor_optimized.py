"""
Optimized Query Processor
Extends baseline QueryProcessor with Cross-Encoder reranking and RRF fusion.
"""

import asyncio
from typing import List, Dict, Any, Optional

from query_processor import QueryProcessor
from batch_manager import BatchManager
from utils.fusion import reciprocal_rank_fusion
from utils.reranker import CrossEncoderReranker
from config.optimization_settings import optimization_settings
from config.settings import settings as config


class OptimizedQueryProcessor(QueryProcessor):
    """
    Optimized RAG pipeline with advanced retrieval techniques.
    
    Enhancements over baseline:
    1. Reciprocal Rank Fusion (RRF) for combining FAISS + BM25
    2. Cross-Encoder reranking for semantic relevance scoring
    3. Domain-specific heuristic reranking (inherited from baseline)
    
    Pipeline Flow:
    1. Query expansion (inherited)
    2. FAISS search (large pool, e.g., 100 candidates)
    3. BM25 search (large pool, e.g., 100 candidates)
    4. RRF fusion (combine FAISS + BM25)
    5. Cross-Encoder reranking (semantic scoring)
    6. Domain heuristic reranking (insurance-specific, inherited)
    7. Return top_k results
    """
    
    def __init__(self, batch_manager: BatchManager):
        """
        Initialize optimized pipeline.
        
        Args:
            batch_manager: Batch manager instance (same as baseline)
        """
        super().__init__(batch_manager)
        
        # Initialize cross-encoder reranker if enabled
        self.reranker = None
        if optimization_settings.USE_CROSS_ENCODER:
            print("[OptimizedQueryProcessor] Initializing Cross-Encoder...")
            self.reranker = CrossEncoderReranker(
                model_name=optimization_settings.CROSS_ENCODER_MODEL,
                device=optimization_settings.CROSS_ENCODER_DEVICE,
                batch_size=optimization_settings.CROSS_ENCODER_BATCH_SIZE,
                max_length=optimization_settings.CROSS_ENCODER_MAX_LENGTH
            )
            print(f"[OptimizedQueryProcessor] Cross-Encoder ready: {self.reranker.get_model_info()}")
        else:
            print("[OptimizedQueryProcessor] Cross-Encoder disabled (USE_CROSS_ENCODER=false)")
    
    def _run_retrieval_sync(
        self,
        query: str,
        batch_id: str,
        user_profile: Optional[Dict] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Optimized synchronous retrieval pipeline.
        
        Overrides baseline to integrate RRF fusion and cross-encoder reranking.
        
        Args:
            query: User query
            batch_id: Batch ID to search within
            user_profile: Optional user profile for personalization
            top_k: Number of final results to return
        
        Returns:
            List of reranked documents
        """
        target_batch = batch_id or self.batch_manager.get_default_batch()
        if not target_batch:
            raise ValueError("No batch specified and no default batch set.")

        if not self._ensure_batch_loaded(target_batch):
            raise RuntimeError(f"Failed to load batch '{target_batch}'.")

        # Step 1: Query expansion (inherited from baseline)
        expanded_query = self._expand_query(query)
        is_personal_batch = target_batch.startswith("user_")

        # Step 2 & 3: Retrieve large candidate pool from FAISS and BM25
        # Use larger pool size to give reranker more candidates
        search_pool_size = max(
            optimization_settings.RERANK_TOP_K,  # Optimization setting (default 100)
            config.SEARCH_TOP_K,  # Baseline setting (default 60)
            top_k * 10  # Dynamic: at least 10x final output
        )
        
        print(f"[OptimizedQueryProcessor] Retrieving {search_pool_size} candidates...")

        if is_personal_batch and user_profile:
            # For multi-policy searches, use baseline's multi-policy logic
            num_policies = len(user_profile.get("insurance_policies", {}) or {"default": None})
            chunks_per_policy = max(search_pool_size // max(num_policies, 1), 10)
            
            raw_results = self._multi_policy_search(
                query=query,
                expanded_query=expanded_query,
                user_profile=user_profile,
                chunks_per_policy=chunks_per_policy,
            )
        else:
            # Standard search: get separate FAISS and BM25 results for RRF fusion
            if optimization_settings.USE_RRF_FUSION:
                raw_results = self._hybrid_search_with_rrf(
                    expanded_query,
                    search_pool_size
                )
            else:
                # Fallback to baseline weighted sum fusion
                raw_results = self.search_engine.hybrid_search(
                    query=expanded_query,
                    top_k=search_pool_size
                )

        # Step 4: Deduplicate (inherited from baseline)
        unique_results = self._deduplicate_results(raw_results)
        
        print(f"[OptimizedQueryProcessor] After deduplication: {len(unique_results)} candidates")

        # Step 5: Cross-Encoder reranking (NEW - semantic scoring)
        if self.reranker and optimization_settings.USE_CROSS_ENCODER:
            print(f"[OptimizedQueryProcessor] Applying Cross-Encoder reranking...")
            unique_results = self.reranker.rerank(
                query=query,
                candidates=unique_results,
                top_k=None,  # Keep all, will filter later
                score_field="cross_encoder_score"
            )
            print(f"[OptimizedQueryProcessor] Cross-Encoder reranking complete")

        # Step 6: Domain heuristic reranking (inherited from baseline)
        # This applies insurance-specific boosting on top of cross-encoder scores
        reranked_results = self._rerank_insurance_results(
            query,
            unique_results,
            max_results=top_k
        )
        
        print(f"[OptimizedQueryProcessor] Final results: {len(reranked_results)}")

        return reranked_results

    def _hybrid_search_with_rrf(
        self,
        query: str,
        top_k: int
    ) -> List[Dict[str, Any]]:
        """
        Perform hybrid search using RRF fusion instead of weighted sum.
        
        Args:
            query: Expanded search query
            top_k: Number of candidates to retrieve
        
        Returns:
            Combined results using RRF
        """
        # Get separate FAISS and BM25 results
        faiss_results = self.search_engine._faiss_search(query, top_k)
        bm25_results = self.search_engine._bm25_search(query, top_k)
        
        print(f"[OptimizedQueryProcessor] RRF Fusion: {len(faiss_results)} FAISS + {len(bm25_results)} BM25")
        
        # Apply RRF fusion
        combined_results = reciprocal_rank_fusion(
            faiss_results=faiss_results,
            bm25_results=bm25_results,
            k=optimization_settings.RRF_K_CONSTANT,
            top_k=top_k
        )
        
        return combined_results
    
    def get_pipeline_info(self) -> Dict[str, Any]:
        """
        Return information about the optimized pipeline configuration.
        
        Returns:
            Dictionary with pipeline settings and status
        """
        info = {
            "pipeline_type": "optimized",
            "cross_encoder_enabled": optimization_settings.USE_CROSS_ENCODER,
            "rrf_fusion_enabled": optimization_settings.USE_RRF_FUSION,
            "rerank_pool_size": optimization_settings.RERANK_TOP_K,
        }
        
        if self.reranker:
            info["cross_encoder_model"] = self.reranker.get_model_info()
        
        if optimization_settings.USE_RRF_FUSION:
            info["rrf_k_constant"] = optimization_settings.RRF_K_CONSTANT
        
        return info
