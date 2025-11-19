## Repo quick-orientation for AI coding agents

This file is a compact, actionable guide to become productive in this repository. Keep edits small and runnable; prefer adding tests or scripts rather than long-form changes.

### Big picture (how pieces fit)
- `main.py` — CLI entry point for asking questions (uses `QueryProcessor`).
- `setup_batch.py` — ingest documents and build a batch (FAISS + BM25). Result: `batches/<batch>/faiss_index` + `bm25_index.pkl` + `metadata.json`.
- `batch_manager.py` — central batch registry and helpers used by other components.
- `query_processor.py` — retrieval + generation orchestration: uses `utils/search.py` (hybrid FAISS+BM25), then `AsyncOpenAI` for generation in `run_generation`.
- `scripts/evaluate_rag.py` — async evaluation harness using `ragas` (creates `SingleTurnSample` → `EvaluationDataset` → `aevaluate`).
- `utils/` — helpers for embeddings, file parsing, and search logic.

Data flow (short): dataset/tests → QueryProcessor.run_retrieval → QueryProcessor.run_generation → Sample(s) → ragas evaluation → CSV under `evaluation/results/`.

### Key files to read before editing
- `config/settings.py` — tunables (chunk sizes, faiss/bm25 weights, response params).
- `query_processor.py` — where retrieval & prompt construction live; crucial when changing doc/response behaviour.
- `utils/search.py` & `utils/embeddings.py` — where indexes and embeddings are used; editing these affects retrieval quality.
- `scripts/evaluate_rag.py` — evaluation pipeline; add/remove metrics here.
- `batch_manager.py` — batch discovery / switching logic; tests and CLI rely on it.

### Developer workflows & commands (PowerShell friendly)
- Install deps: `pip install -r requirements.txt` (use virtualenv).
- Run CLI: `python main.py "Your question"` or `python main.py --batch insurance "Your question"`.
- Create/rebuild a batch: `python setup_batch.py <batch_id>` (or `--rebuild`).
- Run evaluation: `python -m scripts.evaluate_rag --dataset tests/data/golden_dataset.json --batch my_policies --output evaluation/results/ragas_evaluation.csv`.
- Quick checks: `python -m scripts.evaluate_rag -h` (validates import-time safety), `python -m compileall scripts/evaluate_rag.py`.
- Run tests: `python tests/test_queries.py --batch insurance` (or run `pytest tests/`).

### Terminal command syntax (PowerShell)

When asking Copilot (or another agent) to produce shell commands for this repo, always ensure the commands are PowerShell-friendly. Common mistakes we've seen produce SyntaxError or parser errors in PowerShell; follow these rules to avoid them:

- Do NOT use bash-style heredocs or redirection like `<<'PY'` — PowerShell doesn't support that syntax. For multi-line Python logic prefer creating a small `.py` script and running it, or use `python -c "..."` for short one-liners.
- When chaining commands on one line, use `;` (semicolon) in PowerShell. Example (safe):

```powershell
cd "C:\Users\ianko\Python Files\domain-agnostic-chatbot"; python .\scripts\inspect_ragas.py
```

- For Python one-liners use double quotes outside and single quotes inside where necessary. Example (safe):

```powershell
python -c "import os; print(os.getenv('OPENAI_API_KEY'))"
```

- To run a virtualenv activation script use the call operator `&` with a quoted path:

```powershell
& "C:\Users\ianko\Python Files\domain-agnostic-chatbot\.venv_eval\Scripts\Activate.ps1"
```

- Set temporary environment variables in the current session like:

```powershell
$env:OPENAI_API_KEY = 'sk-...'
python -m scripts.evaluate_rag --dataset tests/data/golden_dataset.json --batch my_policies --output evaluation/results/out.csv
```

- For persistent env vars use `setx` (note: requires reopening shell to take effect):

```powershell
setx OPENAI_API_KEY 'sk-...'
```

- When requesting commands from Copilot, always state the target shell (PowerShell) and prefer explicit script invocation over inline heredocs. If a snippet is long, ask the agent to create a `.py` helper under `scripts/` and then run it.

- Avoid using backticks (`) in the commands because PowerShell treats them as escape characters. If you need to show backticks, wrap the command in a fenced code block and mark the language as `powershell` so it's clear.

Examples of what to avoid (PowerShell will error):

```powershell
# BAD (bash heredoc; will produce "The '<' operator is reserved for future use" in PowerShell):
cd "C:\Users\ianko\Python Files\domain-agnostic-chatbot"; python - <<'PY'
print('hello')
PY
```

If you want alternative examples for bash/WSL or macOS shells, tell me which shell and I'll add a short block for that shell as well.

### Project-specific conventions & gotchas
- Batches must contain both FAISS directory and a `bm25_index.pkl`. `BatchManager.switch_batch()` returns False if files missing.
- Many modules use async (asyncio) but still call blocking code inside thread executors (see `QueryProcessor._run_retrieval_sync`) — avoid introducing long blocking calls into asyncio paths.
- Logging is lightweight `print()` with tags like `[DEBUG]`, `[INFO]`, `[WARN]`. Keep this pattern when adding quick debug traces.
- Ragas metrics are version-sensitive: prefer safe imports. Example pattern used in repo:

```py
try:
    from ragas.metrics import Faithfulness
except ImportError:
    from ragas.metrics.collections import Faithfulness
```

- LLM factory: use `ragas.llms.llm_factory(model, provider='openai', client=...)`. The repo has code that passes a provider and an AsyncOpenAI client (see `scripts/evaluate_rag.py`).
- `QueryProcessor.run_generation` uses `AsyncOpenAI.chat.completions.create(...)` and expects `response.choices[0].message.content` — be mindful if changing OpenAI SDK usage.

### Integration points & dependencies
- OpenAI: `OPENAI_API_KEY` is required (stored in `.env` or set in environment). For PowerShell: `$env:OPENAI_API_KEY = 'sk-...'` (temporary) or `setx OPENAI_API_KEY 'sk-...'` for persistence.
- Ragas (evaluation): scripts use `ragas>=0.3.9`. Metrics API moved historically between `ragas.metrics` and `ragas.metrics.collections` — use the fallback import pattern.
- FAISS indexes and BM25 require platform-native dependencies (`faiss-cpu`) — ensure local dev environment matches requirements.

### How to add a new evaluation metric
1. Import metric (use the safe import pattern above).
2. Add to `metric_suite` in `scripts/evaluate_rag.py`.
3. Run `python -m scripts.evaluate_rag --dataset tests/data/golden_dataset.json --batch my_policies --output evaluation/results/new.csv` to validate.

### Common debugging tips
- If `aevaluate` jobs raise AttributeError like `InstructorLLM object has no attribute 'agenerate_prompt'`: this is usually a mismatch between Ragas and the chosen LLM wrapper. Remedies:
  - Check installed ragas version: `python -c "import ragas; print(ragas.__version__)"`.
  - Try a different `provider` value for `llm_factory` or use the OpenAI provider with `AsyncOpenAI` client.
  - Use `scripts/inspect_ragas.py` (provided) to list available metrics/collections.
- If a batch fails to load: inspect `batches/<batch>/metadata.json` and ensure `faiss_index` and `bm25_index.pkl` exist. Re-run `setup_batch.py` to rebuild.

### Small editing rules for AI agents
- Keep edits focused and runnable: add unit/functional tests where possible.
- Preserve existing debug print tags and CLI behavior; update `-h` help text if flags change.
- Avoid editing embedding models or chunking defaults silently; surface these changes in `config/settings.py` and README.

If anything here is unclear or you want the doc to be tuned for a narrower task (e.g., only evaluation or only the React UI), tell me which focus and I will iterate.
