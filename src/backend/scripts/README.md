# Scripts Directory - RAG Evaluation Tools

This directory contains utilities for evaluating and testing the RAG pipeline.

## Files

### evaluate_rag.py
Main evaluation framework using RAGAS metrics.

**Features:**

**Usage:**
```bash
python evaluate_rag.py
```

### quickstart_evaluation.py
Beginner-friendly quick start script with example usage.

**Features:**

**Usage:**
```bash
# Quick start (recommended for first run)
python -m scripts.evaluate_rag --dataset tests/data/golden_dataset.json --batch my_policies --output evaluation/results/ragas_evaluation.csv
```
<!-- Removed: temporary verification helper used during dataset debugging. -->

### golden_dataset.json
Reference dataset containing ground truth Q&A pairs for evaluation.

**Contents:**

**Format:**
```json
{
  "version": "1.0",
  "timestamp": "2025-11-18",
  "qa_pairs": [
    {
      "id": "q001",
      "question": "...",
      "ground_truth": "...",
      "context": "...",
      "difficulty": "..."
    }
  ]
}
```

## Setup

### 1. Install Dependencies
```bash
pip install -r ../requirements.txt
```

This installs:
- `datasets==3.0.0` - Dataset handling
- `langchain-openai>=1.0.3` - LLM integration (compatible with openai 2.x)
- `ragas` (via evaluate_rag.py imports) - Evaluation metrics

### 2. Prepare Environment
Ensure these files exist:
- `/query_processor.py` - With new async methods
- `/config/settings.py` - Configuration
- `./golden_dataset.json` - Evaluation dataset

### 3. Run Evaluation
```bash
# Full evaluation — no user profile by default
python -m scripts.evaluate_rag --dataset tests/data/golden_dataset.json --batch my_policies --output evaluation/results/ragas_evaluation.csv

# To explicitly evaluate with a user profile (opt-in only):
python -m scripts.evaluate_rag --dataset tests/data/golden_dataset.json --batch user_3 --output evaluation/results/ragas_with_profile.csv --profile test_data/user_profile.json
```

## Extending the Evaluator

### Add New Metrics
```python
from ragas.metrics import metric_name

class RAGEvaluator:
    async def evaluate_custom(self, ...):
        # Add new metric to evaluation
        result = await evaluate(
            dataset,
            metrics=[metric_name, ...]
        )
        return result
```

### Expand Golden Dataset
Add new Q&A pairs to `golden_dataset.json`:
```json
{
  "id": "q006",
  "question": "New question?",
  "ground_truth": "Ground truth answer",
  "context": "Keywords for retrieval",
  "difficulty": "hard"
}
```

### Integrate with QueryProcessor
```python
from query_processor import QueryProcessor

processor = QueryProcessor(batch_manager)

# Retrieve
docs = await processor.run_retrieval(
    query=question,
    batch_id="batch_id"
)

# Generate
answer = await processor.run_generation(
    query=question,
    search_results=docs
)

# Evaluate
evaluator = RAGEvaluator()
results = await evaluator.evaluate_full_pipeline(
    questions=[question],
    contexts=[[doc["content"] for doc in docs]],
    answers=[answer],
    ground_truths=[ground_truth]
)
```

## Metrics Explained

- **Faithfulness**: Does the generated answer stay true to the retrieved context?
- **Answer Relevancy**: Is the generated answer relevant to the question?
- **Context Precision**: Are the retrieved contexts relevant to the question?
- **Context Recall**: Are all relevant contexts retrieved?

## Output

Results are saved to `../evaluation/results.json`:
```json
{
  "faithfulness": 0.85,
  "answer_relevancy": 0.92,
  "context_precision": 0.88,
  "context_recall": 0.80
}
```

## Troubleshooting

### Golden Dataset Not Found
- Ensure `golden_dataset.json` is in the scripts directory
- Or place it in `tests/data/golden_dataset.json`

### RAGAS Import Errors
- Run `pip install ragas`
- Verify installation: `python -c "import ragas; print(ragas.__version__)"`

### OpenAI API Errors
- Ensure `OPENAI_API_KEY` environment variable is set
- Verify API key is valid and has sufficient quota

### Async Errors
- Run scripts with `python` (not `python -m`)
- Ensure using Python 3.7+

## Performance Notes

- First evaluation run may be slow (initializes RAGAS)
- Subsequent runs are faster
- For large datasets, consider batch processing
- LLM calls during evaluation will consume API credits

## Next Steps

1. Expand golden dataset with more domain-specific examples
2. Run evaluation after each RAG pipeline update
3. Track metrics over time for regression detection
4. Use results to identify optimization opportunities
5. Implement CI/CD integration for automated evaluation
