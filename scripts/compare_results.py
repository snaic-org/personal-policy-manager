"""
scripts/compare_results.py

Analysis and visualization tools for comparing baseline vs optimized pipeline results.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional

import pandas as pd
import numpy as np


def compute_statistical_summary(comparison_csv: str) -> pd.DataFrame:
    """
    Compute aggregate statistics from comparison CSV.
    
    Args:
        comparison_csv: Path to comparison CSV file
    
    Returns:
        DataFrame with statistical summary
    """
    df = pd.read_csv(comparison_csv)
    
    # Find metric columns (those with baseline_, optimized_, delta_ prefixes)
    metric_names = set()
    for col in df.columns:
        if col.startswith("baseline_"):
            metric_names.add(col.replace("baseline_", ""))
        elif col.startswith("optimized_"):
            metric_names.add(col.replace("optimized_", ""))
        elif col.startswith("delta_"):
            metric_names.add(col.replace("delta_", ""))
    
    # Compute statistics for each metric
    stats_data = []
    for metric in metric_names:
        baseline_col = f"baseline_{metric}"
        optimized_col = f"optimized_{metric}"
        delta_col = f"delta_{metric}"
        
        if baseline_col in df.columns and optimized_col in df.columns:
            baseline_vals = df[baseline_col].dropna()
            optimized_vals = df[optimized_col].dropna()
            delta_vals = df[delta_col].dropna() if delta_col in df.columns else optimized_vals - baseline_vals
            
            # Compute statistics
            stats_data.append({
                "metric": metric,
                "baseline_mean": baseline_vals.mean(),
                "baseline_median": baseline_vals.median(),
                "baseline_std": baseline_vals.std(),
                "optimized_mean": optimized_vals.mean(),
                "optimized_median": optimized_vals.median(),
                "optimized_std": optimized_vals.std(),
                "delta_mean": delta_vals.mean(),
                "delta_median": delta_vals.median(),
                "delta_std": delta_vals.std(),
                "improvement_pct": ((optimized_vals.mean() - baseline_vals.mean()) / baseline_vals.mean() * 100) if baseline_vals.mean() != 0 else 0,
                "samples_improved": (delta_vals > 0).sum(),
                "samples_degraded": (delta_vals < 0).sum(),
                "samples_unchanged": (delta_vals == 0).sum(),
            })
    
    stats_df = pd.DataFrame(stats_data)
    
    # Try to compute statistical significance (paired t-test)
    try:
        from scipy import stats
        
        for idx, row in stats_df.iterrows():
            metric = row["metric"]
            baseline_col = f"baseline_{metric}"
            optimized_col = f"optimized_{metric}"
            
            if baseline_col in df.columns and optimized_col in df.columns:
                baseline_vals = df[baseline_col].dropna()
                optimized_vals = df[optimized_col].dropna()
                
                # Paired t-test
                if len(baseline_vals) == len(optimized_vals) and len(baseline_vals) > 1:
                    t_stat, p_value = stats.ttest_rel(optimized_vals, baseline_vals)
                    stats_df.at[idx, "t_statistic"] = t_stat
                    stats_df.at[idx, "p_value"] = p_value
                    stats_df.at[idx, "significant"] = "Yes" if p_value < 0.05 else "No"
    except ImportError:
        print("[WARN] scipy not installed. Skipping statistical significance tests.")
        print("       Install with: pip install scipy>=1.9.0")
    
    return stats_df


def generate_comparison_report(
    comparison_csv: str,
    output_md: Optional[str] = None
) -> str:
    """
    Generate markdown report from comparison CSV.
    
    Args:
        comparison_csv: Path to comparison CSV file
        output_md: Optional path to save markdown report
    
    Returns:
        Markdown report as string
    """
    comparison_csv = Path(comparison_csv)
    if not comparison_csv.exists():
        raise FileNotFoundError(f"Comparison CSV not found: {comparison_csv}")
    
    df_comparison = pd.read_csv(comparison_csv)
    stats_df = compute_statistical_summary(str(comparison_csv))
    
    # Build markdown report
    lines = []
    lines.append("# RAG Pipeline Comparison Report")
    lines.append("")
    lines.append(f"**Comparison File:** `{comparison_csv.name}`")
    lines.append(f"**Number of Samples:** {len(df_comparison)}")
    lines.append("")
    
    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    
    # Winner count
    if "winner" in df_comparison.columns:
        winner_counts = df_comparison["winner"].value_counts().to_dict()
        total = len(df_comparison)
        
        optimized_wins = winner_counts.get("optimized", 0)
        baseline_wins = winner_counts.get("baseline", 0)
        ties = winner_counts.get("tie", 0)
        
        lines.append(f"- **Optimized Pipeline Wins:** {optimized_wins} ({optimized_wins/total*100:.1f}%)")
        lines.append(f"- **Baseline Pipeline Wins:** {baseline_wins} ({baseline_wins/total*100:.1f}%)")
        lines.append(f"- **Ties:** {ties} ({ties/total*100:.1f}%)")
        lines.append("")
        
        if optimized_wins > baseline_wins:
            lines.append("✅ **Conclusion:** Optimized pipeline outperforms baseline overall.")
        elif baseline_wins > optimized_wins:
            lines.append("⚠️ **Conclusion:** Baseline pipeline outperforms optimized overall.")
        else:
            lines.append("🔄 **Conclusion:** Both pipelines perform similarly overall.")
        lines.append("")
    
    # Per-Metric Breakdown
    lines.append("## Per-Metric Breakdown")
    lines.append("")
    
    lines.append("| Metric | Baseline | Optimized | Improvement | Significance |")
    lines.append("|--------|----------|-----------|-------------|--------------|")
    
    for _, row in stats_df.iterrows():
        metric = row["metric"]
        baseline_mean = row["baseline_mean"]
        optimized_mean = row["optimized_mean"]
        improvement_pct = row["improvement_pct"]
        
        # Significance indicator
        sig_str = ""
        if "significant" in row and pd.notna(row["significant"]):
            if row["significant"] == "Yes":
                sig_str = f"✓ (p={row['p_value']:.3f})"
            else:
                sig_str = f"✗ (p={row['p_value']:.3f})"
        
        # Improvement indicator
        if improvement_pct > 0:
            improvement_str = f"+{improvement_pct:.1f}% ▲"
        elif improvement_pct < 0:
            improvement_str = f"{improvement_pct:.1f}% ▼"
        else:
            improvement_str = "0.0% ―"
        
        lines.append(f"| {metric} | {baseline_mean:.4f} | {optimized_mean:.4f} | {improvement_str} | {sig_str} |")
    
    lines.append("")
    
    # Detailed Statistics
    lines.append("## Detailed Statistics")
    lines.append("")
    
    for _, row in stats_df.iterrows():
        metric = row["metric"]
        lines.append(f"### {metric}")
        lines.append("")
        lines.append(f"- **Baseline:** μ={row['baseline_mean']:.4f}, σ={row['baseline_std']:.4f}, median={row['baseline_median']:.4f}")
        lines.append(f"- **Optimized:** μ={row['optimized_mean']:.4f}, σ={row['optimized_std']:.4f}, median={row['optimized_median']:.4f}")
        lines.append(f"- **Delta:** μ={row['delta_mean']:.4f}, σ={row['delta_std']:.4f}, median={row['delta_median']:.4f}")
        lines.append(f"- **Samples Improved:** {int(row['samples_improved'])}")
        lines.append(f"- **Samples Degraded:** {int(row['samples_degraded'])}")
        lines.append("")
    
    # Sample-Level Analysis
    lines.append("## Sample-Level Analysis")
    lines.append("")
    
    # Find most improved and most degraded samples
    if "winner" in df_comparison.columns:
        # Calculate average improvement per sample
        metric_cols = [col.replace("delta_", "") for col in df_comparison.columns if col.startswith("delta_")]
        delta_cols = [f"delta_{m}" for m in metric_cols]
        
        df_comparison["avg_delta"] = df_comparison[delta_cols].mean(axis=1)
        
        # Most improved
        most_improved = df_comparison.nlargest(3, "avg_delta")
        lines.append("### Most Improved Samples")
        lines.append("")
        for idx, row in most_improved.iterrows():
            sample_id = row.get("sample_id", idx + 1)
            question = row.get("question", "N/A")[:80]
            avg_delta = row["avg_delta"]
            lines.append(f"- **Sample {sample_id}** (Δ={avg_delta:.4f}): {question}...")
        lines.append("")
        
        # Most degraded
        most_degraded = df_comparison.nsmallest(3, "avg_delta")
        lines.append("### Most Degraded Samples")
        lines.append("")
        for idx, row in most_degraded.iterrows():
            sample_id = row.get("sample_id", idx + 1)
            question = row.get("question", "N/A")[:80]
            avg_delta = row["avg_delta"]
            lines.append(f"- **Sample {sample_id}** (Δ={avg_delta:.4f}): {question}...")
        lines.append("")
    
    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    
    # Calculate overall improvement
    overall_improvement = stats_df["improvement_pct"].mean()
    
    if overall_improvement > 5:
        lines.append("✅ **Deploy Optimized Pipeline:** Significant improvements across metrics.")
    elif overall_improvement > 0:
        lines.append("⚠️ **Consider Optimized Pipeline:** Modest improvements, evaluate trade-offs (latency, cost).")
    else:
        lines.append("❌ **Stick with Baseline:** Optimized pipeline shows no clear advantage.")
    
    lines.append("")
    lines.append("---")
    lines.append(f"*Report generated by `scripts/compare_results.py`*")
    
    # Join all lines
    report = "\n".join(lines)
    
    # Save if output path provided
    if output_md:
        output_path = Path(output_md)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"[INFO] Markdown report saved to: {output_path}")
    
    return report


def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Analyze and visualize comparison results"
    )
    parser.add_argument("--comparison", required=True, help="Path to comparison CSV file")
    parser.add_argument("--output", default=None, help="Output directory for analysis results (default: same as comparison CSV)")
    parser.add_argument("--format", choices=["markdown", "json", "both"], default="both", help="Output format")
    
    args = parser.parse_args()
    
    comparison_path = Path(args.comparison)
    if not comparison_path.exists():
        print(f"[ERROR] Comparison CSV not found: {comparison_path}")
        return
    
    # Determine output directory
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = comparison_path.parent
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Compute statistics
    print("[INFO] Computing statistical summary...")
    stats_df = compute_statistical_summary(str(comparison_path))
    
    # Save statistics as JSON
    if args.format in ["json", "both"]:
        stats_json = output_dir / "statistics_summary.json"
        stats_dict = stats_df.to_dict(orient="records")
        with open(stats_json, "w") as f:
            json.dump(stats_dict, f, indent=2)
        print(f"[INFO] Statistics saved to: {stats_json}")
    
    # Generate markdown report
    if args.format in ["markdown", "both"]:
        output_md = output_dir / "comparison_report.md"
        print("[INFO] Generating markdown report...")
        report = generate_comparison_report(str(comparison_path), str(output_md))
        print("\n" + "=" * 80)
        print(report)
        print("=" * 80)
    
    # Print summary table
    print("\n[INFO] Statistical Summary:")
    print(stats_df.to_string(index=False))
    
    print(f"\n[INFO] Analysis complete. Results saved to: {output_dir}")


if __name__ == "__main__":
    main()
