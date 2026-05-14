# config/optimization_settings.py

"""
Optimization Settings for Advanced RAG Pipeline
Configurations for Cross-Encoder reranking and Reciprocal Rank Fusion (RRF).
"""

import os

class OptimizationSettings:
    """Settings for optimized RAG pipeline components."""

    def __init__(self):
        # ============================================
        # CROSS-ENCODER RERANKING SETTINGS
        # ============================================
        
        # Model selection: Fast, balanced, or high-accuracy
        # Options (based on 2025 benchmarks):
        #   - cross-encoder/ms-marco-MiniLM-L-6-v2 (90MB, excellent speed/accuracy balance - DEFAULT)
        #   - bge-reranker-base (strong accuracy, moderate compute)
        #   - cross-encoder/ms-marco-MiniLM-L-12-v2 (120MB, higher accuracy)
        #   - zerank-1 (best-in-class accuracy, slower)
        # Research shows ms-marco-MiniLM-L-6-v2 provides optimal prod performance with NDCG@10 ~0.82+
        self.CROSS_ENCODER_MODEL = os.getenv(
            "CROSS_ENCODER_MODEL",
            "cross-encoder/ms-marco-MiniLM-L-6-v2"
        )
        
        # Batch size for cross-encoder processing
        self.CROSS_ENCODER_BATCH_SIZE = int(os.getenv("CROSS_ENCODER_BATCH_SIZE", "16"))
        
        # Maximum token length for cross-encoder input
        self.CROSS_ENCODER_MAX_LENGTH = int(os.getenv("CROSS_ENCODER_MAX_LENGTH", "512"))
        
        # Device: "cpu" or "cuda" (if GPU available)
        self.CROSS_ENCODER_DEVICE = os.getenv("CROSS_ENCODER_DEVICE", "cpu")
        
        # ============================================
        # RECIPROCAL RANK FUSION (RRF) SETTINGS
        # ============================================
        
        # RRF k constant (research-backed optimal value: 60)
        # Lower k (20-40): More weight to top-ranked items
        # Higher k (60-100): More democratic fusion, better for diverse sources
        # Default 60 is robust across diverse retrieval pipelines per 2025 benchmarks
        self.RRF_K_CONSTANT = int(os.getenv("RRF_K_CONSTANT", "60"))
        
        # ============================================
        # RERANKING PIPELINE SETTINGS
        # ============================================
        
        # Size of candidate pool to retrieve before reranking
        # Research shows 25-50 candidates balances recall and computation cost
        # 25 for general use, 50 for knowledge-intensive systems favoring recall
        # Reduced from 100 to 25 based on empirical best practices
        self.RERANK_TOP_K = int(os.getenv("RERANK_TOP_K", "25"))
        
        # Final number of results to return after all reranking stages
        self.RERANK_OUTPUT_K = int(os.getenv("RERANK_OUTPUT_K", "10"))
        
        # ============================================
        # FEATURE FLAGS
        # ============================================
        
        # Enable/disable cross-encoder reranking
        self.USE_CROSS_ENCODER = os.getenv("USE_CROSS_ENCODER", "true").lower() == "true"
        
        # Enable/disable RRF fusion (if False, uses weighted sum from baseline)
        self.USE_RRF_FUSION = os.getenv("USE_RRF_FUSION", "true").lower() == "true"
        
        # Enable optimized pipeline globally
        self.ENABLE_OPTIMIZED_PIPELINE = os.getenv("ENABLE_OPTIMIZED_PIPELINE", "false").lower() == "true"

    def get_config_summary(self):
        """Return a dictionary of current optimization settings."""
        return {
            "cross_encoder_model": self.CROSS_ENCODER_MODEL,
            "cross_encoder_batch_size": self.CROSS_ENCODER_BATCH_SIZE,
            "cross_encoder_max_length": self.CROSS_ENCODER_MAX_LENGTH,
            "cross_encoder_device": self.CROSS_ENCODER_DEVICE,
            "rrf_k_constant": self.RRF_K_CONSTANT,
            "rerank_top_k": self.RERANK_TOP_K,
            "rerank_output_k": self.RERANK_OUTPUT_K,
            "use_cross_encoder": self.USE_CROSS_ENCODER,
            "use_rrf_fusion": self.USE_RRF_FUSION,
            "optimized_pipeline_enabled": self.ENABLE_OPTIMIZED_PIPELINE,
        }


# Create a global settings instance
optimization_settings = OptimizationSettings()
