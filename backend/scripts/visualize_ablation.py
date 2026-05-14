"""
scripts/visualize_ablation.py

Create visualizations for ablation study results.
"""

import pandas as pd
import json
from pathlib import Path


def analyze_ablation_results(ablation_dir: str):
    """
    Analyze and visualize ablation study results.
    
    Args:
        ablation_dir: Directory containing ablation results
    """
    ablation_path = Path(ablation_dir)
    
    # Load comparison data
    comparison_csv = ablation_path / "ablation_comparison.csv"
    if not comparison_csv.exists():
        print(f"Error: {comparison_csv} not found")
        return
    
    df = pd.read_csv(comparison_csv)
    
    # Load summary
    summary_json = ablation_path / "ablation_summary.json"
    if summary_json.exists():
        with open(summary_json) as f:
            summary = json.load(f)
    else:
        summary = {}
    
    print("=" * 80)
    print("ABLATION STUDY ANALYSIS")
    print("=" * 80)
    
    # Key metrics to compare
    metrics = [
        "faithfulness",
        "context_precision", 
        "context_recall",
        "answer_relevancy",
        "semantic_similarity",
        "context_utilization"
    ]
    
    # Filter to only metrics that exist
    metrics = [m for m in metrics if m in df.columns]
    
    print("\n📊 METRIC COMPARISON")
    print("-" * 80)
    
    # Create comparison table
    baseline_row = df[df["configuration"] == "baseline"].iloc[0] if "baseline" in df["configuration"].values else None
    
    for metric in metrics:
        print(f"\n{metric.upper().replace('_', ' ')}:")
        print(f"{'Configuration':<30} {'Score':>10} {'vs Baseline':>15}")
        print("-" * 60)
        
        for _, row in df.iterrows():
            config = row["configuration"]
            score = row[metric]
            
            if baseline_row is not None and config != "baseline":
                baseline_score = baseline_row[metric]
                delta = score - baseline_score
                delta_pct = (delta / baseline_score * 100) if baseline_score != 0 else 0
                delta_str = f"{delta_pct:+6.1f}%"
                
                # Add indicator
                if delta_pct > 5:
                    indicator = "🟢"
                elif delta_pct > 0:
                    indicator = "🔵"
                elif delta_pct < -5:
                    indicator = "🔴"
                else:
                    indicator = "⚪"
            else:
                delta_str = "baseline"
                indicator = "⚫"
            
            print(f"{config:<30} {score:>10.4f} {delta_str:>14} {indicator}")
    
    # Overall ranking
    print("\n\n🏆 OVERALL RANKING (by average score)")
    print("-" * 80)
    
    df["average_score"] = df[metrics].mean(axis=1)
    df_sorted = df.sort_values("average_score", ascending=False)
    
    for rank, (_, row) in enumerate(df_sorted.iterrows(), 1):
        config = row["configuration"]
        avg_score = row["average_score"]
        
        if rank == 1:
            medal = "🥇"
        elif rank == 2:
            medal = "🥈"
        elif rank == 3:
            medal = "🥉"
        else:
            medal = f"{rank}."
        
        print(f"{medal} {config:<30} Avg Score: {avg_score:.4f}")
    
    # Feature contribution analysis
    print("\n\n🔬 FEATURE CONTRIBUTION ANALYSIS")
    print("-" * 80)
    
    if baseline_row is not None:
        configs = {
            "baseline": {"rrf": False, "cross_encoder": False},
            "rrf_only": {"rrf": True, "cross_encoder": False},
            "cross_encoder_only": {"rrf": False, "cross_encoder": True},
            "both": {"rrf": True, "cross_encoder": True},
        }
        
        # Calculate marginal contributions
        baseline_avg = baseline_row["average_score"] if "average_score" in baseline_row else df[df["configuration"] == "baseline"][metrics].mean(axis=1).values[0]
        
        rrf_only_avg = df[df["configuration"] == "rrf_only"][metrics].mean(axis=1).values[0] if "rrf_only" in df["configuration"].values else None
        ce_only_avg = df[df["configuration"] == "cross_encoder_only"][metrics].mean(axis=1).values[0] if "cross_encoder_only" in df["configuration"].values else None
        both_avg = df[df["configuration"] == "both"][metrics].mean(axis=1).values[0] if "both" in df["configuration"].values else None
        
        if rrf_only_avg is not None:
            rrf_contribution = rrf_only_avg - baseline_avg
            rrf_pct = (rrf_contribution / baseline_avg * 100) if baseline_avg != 0 else 0
            print(f"RRF Fusion alone:          {rrf_pct:+6.1f}% ({rrf_contribution:+.4f})")
        
        if ce_only_avg is not None:
            ce_contribution = ce_only_avg - baseline_avg
            ce_pct = (ce_contribution / baseline_avg * 100) if baseline_avg != 0 else 0
            print(f"Cross-Encoder alone:       {ce_pct:+6.1f}% ({ce_contribution:+.4f})")
        
        if both_avg is not None:
            combined_contribution = both_avg - baseline_avg
            combined_pct = (combined_contribution / baseline_avg * 100) if baseline_avg != 0 else 0
            print(f"Both combined:             {combined_pct:+6.1f}% ({combined_contribution:+.4f})")
            
            # Interaction effect
            if rrf_only_avg is not None and ce_only_avg is not None:
                expected_combined = baseline_avg + rrf_contribution + ce_contribution
                interaction = both_avg - expected_combined
                interaction_pct = (interaction / baseline_avg * 100) if baseline_avg != 0 else 0
                print(f"\nInteraction effect:        {interaction_pct:+6.1f}% ({interaction:+.4f})")
                
                if abs(interaction_pct) < 1:
                    print("  → Features are approximately independent")
                elif interaction_pct > 0:
                    print("  → Positive synergy: features work better together")
                else:
                    print("  → Negative interaction: features interfere with each other")
    
    # Recommendations
    print("\n\n💡 RECOMMENDATIONS")
    print("-" * 80)
    
    winner = df_sorted.iloc[0]
    winner_config = winner["configuration"]
    winner_score = winner["average_score"]
    
    if winner_config == "baseline":
        print("✓ Stick with BASELINE pipeline")
        print("  Neither RRF nor Cross-Encoder improves performance on this dataset")
    elif winner_config == "rrf_only":
        print("✓ Use RRF ONLY (disable Cross-Encoder)")
        print("  RRF fusion helps, but Cross-Encoder hurts performance")
    elif winner_config == "cross_encoder_only":
        print("✓ Use CROSS-ENCODER ONLY (disable RRF)")
        print("  Cross-Encoder reranking helps, but RRF fusion hurts performance")
    elif winner_config == "both":
        print("✓ Use BOTH RRF and Cross-Encoder")
        print("  Combined approach achieves best performance")
    
    print(f"\n  Best configuration: {winner_config}")
    print(f"  Average score: {winner_score:.4f}")
    
    # Check if improvement is meaningful
    if baseline_row is not None and winner_config != "baseline":
        improvement = winner_score - baseline_row["average_score"]
        improvement_pct = (improvement / baseline_row["average_score"] * 100) if baseline_row["average_score"] != 0 else 0
        print(f"  Improvement over baseline: {improvement_pct:+.1f}%")
        
        if improvement_pct < 1:
            print("\n  ⚠️  Note: Improvement is marginal (<1%). Consider baseline for simplicity.")
    
    print("\n" + "=" * 80)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze ablation study results")
    parser.add_argument("--results-dir", required=True, help="Directory with ablation results")
    
    args = parser.parse_args()
    
    analyze_ablation_results(args.results_dir)


if __name__ == "__main__":
    main()
