"""
scripts/evaluate_comparison.py

Side-by-side evaluation of baseline vs optimized RAG pipelines.
Runs both pipelines on the same dataset and generates comparison report.
"""

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd

# Import the evaluation function
from scripts.evaluate_rag import evaluate_dataset


async def run_comparison_evaluation(
    dataset_path: str,
    batch_id: str,
    output_dir: str = "evaluation/results/comparison",
    top_k: int = 10,
    evaluator_model: str = "gpt-4o-mini",
    profile_path: str = None,
):
    """
    Run side-by-side evaluation of baseline and optimized pipelines.
    
    Args:
        dataset_path: Path to golden dataset JSON
        batch_id: Batch ID to use for retrieval
        output_dir: Directory for comparison outputs
        top_k: Number of retrieved chunks
        evaluator_model: LLM model for Ragas evaluation
        profile_path: Optional user profile path
    """
    # Create timestamped output directory
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    comparison_dir = Path(output_dir) / timestamp
    comparison_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print(f"BASELINE vs OPTIMIZED PIPELINE COMPARISON")
    print(f"Timestamp: {timestamp}")
    print(f"Dataset: {dataset_path}")
    print(f"Batch: {batch_id}")
    print(f"Output: {comparison_dir}")
    print("=" * 80)
    
    # Define output paths
    baseline_csv = comparison_dir / "baseline_results.csv"
    optimized_csv = comparison_dir / "optimized_results.csv"
    comparison_csv = comparison_dir / "comparison_delta.csv"
    summary_json = comparison_dir / "summary_statistics.json"
    
    # Step 1: Run baseline pipeline evaluation
    print("\n" + "=" * 80)
    print("STEP 1/3: Evaluating BASELINE pipeline")
    print("=" * 80)
    
    try:
        await evaluate_dataset(
            dataset_path=dataset_path,
            batch_id=batch_id,
            output_csv=str(baseline_csv),
            top_k=top_k,
            evaluator_model=evaluator_model,
            provider="openai",
            profile_path=profile_path,
            pipeline="baseline",
        )
        print(f"\n✓ Baseline evaluation complete: {baseline_csv}")
    except Exception as e:
        print(f"\n✗ Baseline evaluation failed: {e}")
        raise
    
    # Step 2: Run optimized pipeline evaluation
    print("\n" + "=" * 80)
    print("STEP 2/3: Evaluating OPTIMIZED pipeline")
    print("=" * 80)
    
    try:
        await evaluate_dataset(
            dataset_path=dataset_path,
            batch_id=batch_id,
            output_csv=str(optimized_csv),
            top_k=top_k,
            evaluator_model=evaluator_model,
            provider="openai",
            profile_path=profile_path,
            pipeline="optimized",
        )
        print(f"\n✓ Optimized evaluation complete: {optimized_csv}")
    except Exception as e:
        print(f"\n✗ Optimized evaluation failed: {e}")
        raise
    
    # Step 3: Generate comparison analysis
    print("\n" + "=" * 80)
    print("STEP 3/3: Generating comparison analysis")
    print("=" * 80)
    
    try:
        comparison_results = generate_comparison(
            baseline_csv,
            optimized_csv,
            comparison_csv,
            summary_json
        )
        print(f"\n✓ Comparison analysis complete: {comparison_csv}")
        print(f"✓ Summary statistics saved: {summary_json}")
    except Exception as e:
        print(f"\n✗ Comparison analysis failed: {e}")
        raise
    
    # Print summary
    print("\n" + "=" * 80)
    print("COMPARISON SUMMARY")
    print("=" * 80)
    print_summary(comparison_results)
    
    print("\n" + "=" * 80)
    print("Comparison evaluation complete!")
    print(f"Results saved to: {comparison_dir}")
    print("=" * 80)
    
    return comparison_results


def generate_comparison(
    baseline_csv: Path,
    optimized_csv: Path,
    output_csv: Path,
    summary_json: Path
) -> Dict[str, Any]:
    """
    Generate comparison analysis from baseline and optimized results.
    
    Args:
        baseline_csv: Path to baseline results CSV
        optimized_csv: Path to optimized results CSV
        output_csv: Path to save comparison CSV
        summary_json: Path to save summary statistics JSON
    
    Returns:
        Dictionary with summary statistics
    """
    # Load both result CSVs
    df_baseline = pd.read_csv(baseline_csv)
    df_optimized = pd.read_csv(optimized_csv)
    
    # Identify metric columns (numeric columns excluding metadata)
    exclude_cols = {"retrieved_count", "top_k", "pipeline"}
    metric_cols = [
        col for col in df_baseline.select_dtypes(include=["number"]).columns
        if col not in exclude_cols
    ]
    
    print(f"\nIdentified metrics: {metric_cols}")
    
    # Create comparison dataframe
    comparison_data = []
    
    for idx in range(len(df_baseline)):
        row = {
            "sample_id": idx + 1,
            "question": df_baseline.iloc[idx].get("question", ""),
        }
        
        # Add baseline and optimized scores for each metric
        for metric in metric_cols:
            baseline_val = df_baseline.iloc[idx].get(metric, 0.0)
            optimized_val = df_optimized.iloc[idx].get(metric, 0.0)
            
            row[f"baseline_{metric}"] = baseline_val
            row[f"optimized_{metric}"] = optimized_val
            row[f"delta_{metric}"] = optimized_val - baseline_val
        
        # Determine winner (higher average metric score)
        baseline_avg = sum(df_baseline.iloc[idx].get(m, 0.0) for m in metric_cols) / len(metric_cols)
        optimized_avg = sum(df_optimized.iloc[idx].get(m, 0.0) for m in metric_cols) / len(metric_cols)
        
        if optimized_avg > baseline_avg + 0.01:  # Small threshold for "tie"
            row["winner"] = "optimized"
        elif baseline_avg > optimized_avg + 0.01:
            row["winner"] = "baseline"
        else:
            row["winner"] = "tie"
        
        comparison_data.append(row)
    
    # Save comparison CSV
    df_comparison = pd.DataFrame(comparison_data)
    df_comparison.to_csv(output_csv, index=False)
    
    # Compute summary statistics
    summary = {
        "timestamp": datetime.now().isoformat(),
        "num_samples": len(df_baseline),
        "metrics": {},
        "overall": {}
    }
    
    for metric in metric_cols:
        baseline_scores = df_baseline[metric].dropna()
        optimized_scores = df_optimized[metric].dropna()
        deltas = df_comparison[f"delta_{metric}"].dropna()
        
        summary["metrics"][metric] = {
            "baseline_mean": float(baseline_scores.mean()),
            "baseline_std": float(baseline_scores.std()),
            "optimized_mean": float(optimized_scores.mean()),
            "optimized_std": float(optimized_scores.std()),
            "mean_delta": float(deltas.mean()),
            "median_delta": float(deltas.median()),
            "improvement_pct": float((optimized_scores.mean() - baseline_scores.mean()) / baseline_scores.mean() * 100) if baseline_scores.mean() > 0 else 0.0,
        }
    
    # Overall win rates
    winner_counts = df_comparison["winner"].value_counts().to_dict()
    total = len(df_comparison)
    
    summary["overall"] = {
        "optimized_wins": winner_counts.get("optimized", 0),
        "baseline_wins": winner_counts.get("baseline", 0),
        "ties": winner_counts.get("tie", 0),
        "optimized_win_rate": winner_counts.get("optimized", 0) / total * 100,
        "baseline_win_rate": winner_counts.get("baseline", 0) / total * 100,
    }
    
    # Save summary JSON
    with open(summary_json, "w") as f:
        json.dump(summary, f, indent=2)
    
    return summary


def print_summary(summary: Dict[str, Any]):
    """Print formatted summary of comparison results."""
    print("\nOverall Win Rates:")
    print(f"  Optimized Wins: {summary['overall']['optimized_wins']} ({summary['overall']['optimized_win_rate']:.1f}%)")
    print(f"  Baseline Wins:  {summary['overall']['baseline_wins']} ({summary['overall']['baseline_win_rate']:.1f}%)")
    print(f"  Ties:           {summary['overall']['ties']}")
    
    print("\nPer-Metric Comparison:")
    print(f"{'Metric':<25} {'Baseline':<12} {'Optimized':<12} {'Improvement':<12}")
    print("-" * 65)
    
    for metric, stats in summary["metrics"].items():
        baseline_mean = stats["baseline_mean"]
        optimized_mean = stats["optimized_mean"]
        improvement_pct = stats["improvement_pct"]
        
        improvement_str = f"{improvement_pct:+.1f}%"
        
        print(f"{metric:<25} {baseline_mean:<12.4f} {optimized_mean:<12.4f} {improvement_str:<12}")


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Run side-by-side comparison of baseline vs optimized RAG pipelines"
    )
    parser.add_argument("--dataset", default="tests/data/golden_dataset.json", help="Path to dataset JSON")
    parser.add_argument("--batch", default="my_policies", help="Batch ID to use for retrieval")
    parser.add_argument("--output", default="evaluation/results/comparison", help="Output directory for comparison results")
    parser.add_argument("--top-k", type=int, default=8, help="Number of retrieved chunks to use")
    parser.add_argument("--evaluator-model", default="gpt-4o-mini", help="LLM model for evaluation")
    parser.add_argument("--profile", default=None, help="Optional path to user profile JSON")
    
    args = parser.parse_args()
    
    asyncio.run(
        run_comparison_evaluation(
            dataset_path=args.dataset,
            batch_id=args.batch,
            output_dir=args.output,
            top_k=args.top_k,
            evaluator_model=args.evaluator_model,
            profile_path=args.profile,
        )
    )


if __name__ == "__main__":
    main()
