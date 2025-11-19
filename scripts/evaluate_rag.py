"""
scripts/evaluate_rag.py

Run RAG evaluation using RAGAS metrics on a small golden dataset.

Notes:
- This script is async (uses ragas LLM factory + AsyncOpenAI client).
- It expects an OPENAI_API_KEY set in your environment or in .env.

Usage (example):
  python -m scripts.evaluate_rag --batch user_3 --output evaluation/results/ragas_evaluation.csv

"""
import asyncio
import csv
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional, cast

import pandas as pd

from openai import AsyncOpenAI
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from ragas import EvaluationDataset, SingleTurnSample, aevaluate
from ragas.dataset_schema import SingleTurnSampleOrMultiTurnSample
from ragas.llms import llm_factory
from ragas.llms.base import BaseRagasLLM, LangchainLLMWrapper
from ragas.run_config import RunConfig
from ragas.embeddings.base import BaseRagasEmbeddings
# from ragas.embeddings.base import embedding_factory
try:
    # Preferred location for Ragas' latest versions
    from ragas.metrics import (
        Faithfulness,
        ContextPrecision,
        ContextRecall,
        AnswerRelevancy,
        SemanticSimilarity,
        ContextUtilization,
    )
except ImportError:
    # Backwards-compatible fallback for older ragas versions
    from ragas.metrics.collections import (
        Faithfulness,
        ContextPrecision,
        ContextRecall,
        AnswerRelevancy,
        SemanticSimilarity,
        ContextUtilization,
    )

from batch_manager import BatchManager
from query_processor import QueryProcessor



# MockResponse and OpenAILLM removed in favor of LangchainLLMWrapper



class HybridEmbeddings(BaseRagasEmbeddings):
    def __init__(self, langchain_embeddings):
        super().__init__()
        self.embeddings = langchain_embeddings

    def embed_query(self, text):
        return self.embeddings.embed_query(text)

    def embed_documents(self, texts):
        return self.embeddings.embed_documents(texts)

    async def aembed_query(self, text):
        return await self.embeddings.aembed_query(text)

    async def aembed_documents(self, texts):
        return await self.embeddings.aembed_documents(texts)

    def embed_text(self, text, **kwargs):
        return self.embeddings.embed_query(text)

    async def aembed_text(self, text, **kwargs):
        return await self.embeddings.aembed_query(text)

    def embed_texts(self, texts, **kwargs):
        return self.embeddings.embed_documents(texts)

    async def aembed_texts(self, texts, **kwargs):
        return await self.embeddings.aembed_documents(texts)

async def evaluate_dataset(
    dataset_path: str,
    batch_id: str,
    output_csv: str,
    top_k: int = 10,
    evaluator_model: str = "gpt-4o-mini",
    provider: str = "openai",
    profile_path: Optional[str] = None,
):
    # Load dataset
    dataset_file = Path(dataset_path)
    if not dataset_file.exists():
        raise FileNotFoundError(f"Dataset file not found: {dataset_file}")

    with dataset_file.open("r", encoding="utf-8") as fh:
        samples = json.load(fh)

    # Init clients - ragas likes AsyncOpenAI
    # Setup the LLM client for ragas. For provider='openai' we require an
    # OPENAI_API_KEY environment variable. If not present, the script will
    # guide the user to set it rather than failing with an obscure exception.
    if provider == "openai" and not os.getenv("OPENAI_API_KEY"):
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Please set it in your environment before running the evaluation."
            " In PowerShell: $env:OPENAI_API_KEY=\"sk-...\" or setx OPENAI_API_KEY \"sk-...\""
        )

    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Use LangchainLLMWrapper to avoid AttributeError: 'InstructorLLM' object has no attribute 'agenerate_prompt'
    # when using llm_factory with Ragas metrics that expect text generation.
    if provider == "openai":
        langchain_llm = ChatOpenAI(model=evaluator_model, api_key=os.getenv("OPENAI_API_KEY"))
        llm = LangchainLLMWrapper(langchain_llm)
    else:
        # Fallback for other providers if needed, though this script focuses on OpenAI
        # If we used llm_factory here, it would return InstructorLLM which might fail with metrics
        # that expect agenerate_prompt. For now, we default to OpenAI/Langchain wrapper.
        print(f"[WARN] Provider '{provider}' requested but script defaults to OpenAI via LangchainLLMWrapper.")
        langchain_llm = ChatOpenAI(model=evaluator_model, api_key=os.getenv("OPENAI_API_KEY"))
        llm = LangchainLLMWrapper(langchain_llm)

    # No adapter needed since we implement agenerate_prompt

    # embeddings for answer relevancy and similarity
    # Use HybridEmbeddings to satisfy both Langchain-style (embed_query) and Ragas-style (embed_text) requirements
    base_embeddings = OpenAIEmbeddings(
        model="text-embedding-3-small", 
        api_key=os.getenv("OPENAI_API_KEY")
    )
    embeddings = HybridEmbeddings(base_embeddings)

    # Metrics (collections API ensures correct async usage per docs)
    faith = Faithfulness(llm=llm)
    ctx_prec = ContextPrecision(llm=llm)
    ctx_recall = ContextRecall(llm=llm)
    ans_rel = AnswerRelevancy(llm=llm, embeddings=embeddings)
    sem_sim = SemanticSimilarity(embeddings=embeddings)
    ctx_util = ContextUtilization(llm=llm)
    metric_suite = [faith, ctx_prec, ctx_recall, ans_rel, sem_sim, ctx_util]

    # Timeouts (seconds) for async operations to avoid indefinite hangs
    METRIC_TIMEOUT = int(os.getenv("METRIC_TIMEOUT", "60"))

    # RunConfig lets ragas handle retries/parallelism, matching docs guidance
    ragas_timeout = int(os.getenv("RAGAS_TIMEOUT", str(METRIC_TIMEOUT)))
    ragas_max_workers = int(os.getenv("RAGAS_MAX_WORKERS", os.getenv("EVAL_CONCURRENCY", "5")))
    ragas_max_retries = int(os.getenv("RAGAS_MAX_RETRIES", "3"))
    ragas_max_wait = int(os.getenv("RAGAS_MAX_WAIT", "60"))
    ragas_seed = int(os.getenv("RAGAS_SEED", "42"))

    run_config = RunConfig(
        timeout=ragas_timeout,
        max_retries=ragas_max_retries,
        max_wait=ragas_max_wait,
        max_workers=ragas_max_workers,
        seed=ragas_seed,
    )
    # Start QueryProcessor
    bm = BatchManager()
    qp = QueryProcessor(bm)

    # Optionally load a user profile to evaluate personal batches (only if
    # a profile path was explicitly provided via the CLI). We no longer
    # automatically load `test_data/user_profile.json` — this prevents the
    # evaluation runner from depending on local test artifacts by default.
    user_profile = None
    if profile_path:
        p = Path(profile_path)
        if p.exists():
            try:
                with p.open("r", encoding="utf-8") as pf:
                    user_profile = json.load(pf)
                    print(f"[DEBUG] Loaded user profile from {p}")
            except Exception as e:
                print(f"[WARN] Failed to load user profile {p}: {e}")
        else:
            print(f"[WARN] Profile path provided but file not found: {p}")

    # Ensure batch loaded
    if not bm.switch_batch(batch_id):
        print(f"Warning: failed to switch to batch {batch_id}. Try a different batch.")

    metadata_rows: List[Dict[str, Any]] = []
    evaluation_samples: List[SingleTurnSampleOrMultiTurnSample] = []

    # Prepare output path and ensure folder exists. We'll save partial results after each sample
    out_path = Path(output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Concurrency control
    CONCURRENCY_LIMIT = int(os.getenv("EVAL_CONCURRENCY", "5"))
    semaphore = asyncio.Semaphore(CONCURRENCY_LIMIT)

    async def process_sample(idx: int, s: Dict[str, Any]) -> Optional[tuple[SingleTurnSample, Dict[str, Any]]]:
        async with semaphore:
            question = s.get("question") or ""
            ground_truth = s.get("ground_truth") or ""
            print(f"[{idx}/{len(samples)}] Evaluating query: {question[:80]}...")

            # Retrieval (with timeout)
            print(f"[DEBUG] Calling run_retrieval for sample {idx}...")
            try:
                search_results = await asyncio.wait_for(
                    qp.run_retrieval(question, batch_id=batch_id, user_profile=user_profile, top_k=top_k),
                    timeout=METRIC_TIMEOUT,
                )
                print(f"[DEBUG] run_retrieval returned {len(search_results)} results for sample {idx}")
            except asyncio.TimeoutError:
                print(f"[ERROR] run_retrieval timed out after {METRIC_TIMEOUT}s for sample {idx}")
                search_results = []
            except Exception as e:
                print(f"Error during retrieval for sample {idx}: {e}")
                search_results = []

            retrieved_texts = [r.get("content", "") for r in search_results]

            # Generation (non-streaming) with timeout
            print(f"[DEBUG] Calling run_generation for sample {idx}...")
            try:
                response_text = await asyncio.wait_for(
                    qp.run_generation(
                        question,
                        search_results,
                        is_personal_batch=bool(user_profile),
                        user_profile=user_profile,
                    ),
                    timeout=METRIC_TIMEOUT,
                )
                print(f"[DEBUG] run_generation returned {len(response_text)} chars for sample {idx}")
            except asyncio.TimeoutError:
                print(f"[ERROR] run_generation timed out after {METRIC_TIMEOUT}s for sample {idx}")
                response_text = ""
            except Exception as e:
                print(f"Error during generation for sample {idx}: {e}")
                response_text = ""

            # Build ragas single-turn input payload & metadata snapshot
            sample_result: Dict[str, Any] = {
                "question": question,
                "ground_truth": ground_truth,
                "response": response_text,
                "retrieved_count": len(retrieved_texts),
                "top_k": top_k,
                "retrieved_contexts": json.dumps(retrieved_texts, ensure_ascii=False),
            }
            ragas_sample = SingleTurnSample(
                user_input=question,
                response=response_text or "",
                reference=ground_truth,
                retrieved_contexts=retrieved_texts,
            )

            print(f"[DEBUG] Finished sample {idx}")
            return ragas_sample, sample_result

    # Create tasks for all samples
    tasks = [process_sample(idx, s) for idx, s in enumerate(samples, 1)]

    processed_pairs = await asyncio.gather(*tasks)
    for pair in processed_pairs:
        if not pair:
            continue
        sample_obj, row = pair
        evaluation_samples.append(sample_obj)
        metadata_rows.append(row)

    if not evaluation_samples:
        print("No samples were processed successfully; aborting evaluation run.")
        return

    eval_dataset = EvaluationDataset(samples=evaluation_samples)
    show_progress = os.getenv("RAGAS_SHOW_PROGRESS", "1").lower() not in {"0", "false", "no"}

    metrics_df = None
    try:
        print("[INFO] Running ragas.aevaluate with official dataset schema...")
        evaluation_result: Any = await aevaluate(
            dataset=eval_dataset,
            metrics=metric_suite,
            run_config=run_config,
            raise_exceptions=False,
            show_progress=show_progress,
        )
        metrics_df = evaluation_result.to_pandas().reset_index(drop=True)
    except Exception as eval_error:
        print(f"[ERROR] RAGAS evaluation failed: {eval_error}")

    df_meta = pd.DataFrame(metadata_rows)
    if metrics_df is not None:
        overlap = set(df_meta.columns) & set(metrics_df.columns)
        metrics_only = metrics_df.drop(columns=list(overlap), errors="ignore")
        final_df = pd.concat([df_meta.reset_index(drop=True), metrics_only], axis=1)
    else:
        final_df = df_meta

    try:
        final_df.to_csv(out_path, index=False)
        print(f"Saved final evaluation results to: {out_path}")

        print("\n=== Evaluation Summary ===")
        metric_cols = [
            col
            for col in final_df.select_dtypes(include=["number"]).columns
            if col not in {"retrieved_count", "top_k"}
        ]
        if metric_cols:
            summary = final_df[metric_cols].mean()
            print(summary)
        else:
            print("No numeric metric columns were produced. Check earlier logs for errors.")
    except Exception as final_write_err:
        print(f"Failed to save final results: {final_write_err}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate RAG pipeline with RAGAS metrics")
    parser.add_argument("--dataset", default="tests/data/golden_dataset.json", help="Path to dataset JSON")
    parser.add_argument("--batch", default="user_3", help="Batch id to use for retrieval")
    parser.add_argument("--output", default="evaluation/results/ragas_evaluation.csv", help="CSV output path")
    parser.add_argument("--top-k", type=int, default=8, help="Number of retrieved chunks to use")
    parser.add_argument("--evaluator-model", default="gpt-4o-mini", help="LLM model for evaluation (llm_factory) - e.g. gpt-4o-mini")
    parser.add_argument("--provider", default="openai", help="LLM provider for ragas llm_factory (openai, oci, haystack, etc.)")
    parser.add_argument("--profile", default=None, help="Optional path to a user profile JSON. If omitted, evaluation will not use a user profile.")

    args = parser.parse_args()

    asyncio.run(
        evaluate_dataset(
            args.dataset,
            args.batch,
            args.output,
            args.top_k,
            args.evaluator_model,
            args.provider,
            profile_path=args.profile,
        )
    )


if __name__ == "__main__":
    main()
