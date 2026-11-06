# Agent-RLS Bench

Reproduction package for *[Experiment, Analysis, and Benchmark] Where Should Row- and Column-Level Permissions Be
Enforced for LLM Data Agents?*

The benchmark compares nine enforcement configurations for LLM data agents that answer questions through multi-step
tool calls over governed relational data. It measures answer leakage, trace noninterference, inference leakage
(linear audit over the policy partition), utility (accuracy, false refusals, Truman-misleading answers) and cost.

## Contents

| Path | Content |
|---|---|
| `code/domains.py`, `code/domains2.py` | The four domains (TPC-H, TPC-DS, BIRD `financial`, enterprise policy model): principals, row predicates, hidden columns, published aggregates, semantic layer, perturbed twins |
| `code/enforce.py` | Enforcement points E0, E2, E3T, E3N, E4, E4M, E5, E6, E7, E8 behind one tool interface; the linear inference auditor |
| `code/agent.py` | Native function-calling agent loop, LLM verifier (E2), output guard (E6), noninterference replay |
| `code/suite.py` | Question suite generator with ground truth |
| `code/run_pilot.py`, `code/run_grid.sh` | Experiment driver (resumable) |
| `code/score.py`, `code/renoni.py`, `code/resecrecy.py`, `code/classify_ni.py` | Scoring; recomputation of trace noninterference and inference leakage from the logs; classification of residual replay differences |
| `code/mechanism.py`, `code/overhead.py` | LLM-free mechanism probes and overhead replay |
| `paper_tools/` | Scripts that generate every number, table and figure of the paper |
| `data/suite.json` | The 169 questions with ground truth |
| `logs/sessions*.jsonl.gz` | Every agent session: tool calls, arguments, responses, final answers, tokens, cost, latency |
| `logs/llm_cache.tar.gz` | Cached LLM responses: re-running the experiments reproduces all sessions without API calls |
| `scripts/` | Database preparation |

## Reproduce the paper's numbers (no API key needed)

```bash
pip install -r requirements.txt
python scripts/prepare_bird.py /path/to/bird/dev_databases/financial/financial.sqlite
python scripts/build_dbs.py
mkdir -p pilot && for f in logs/*.jsonl.gz logs/*.json.gz; do gunzip -c $f > pilot/$(basename ${f%.gz}); done
cp data/suite.json pilot/
python paper_tools/make_numbers.py && python paper_tools/make_figs.py
```

To re-run the agents from the cache, extract `logs/llm_cache.tar.gz` into the package root and run
`code/run_grid.sh`. Every LLM request is served from the cache. To run new models, set `LLM_KEYS_JSON` to a JSON file
of the form `{"<provider>": {"base_url": ..., "api_key": ...}}` and extend `MODELS` in `code/llm.py`.

## Models and logs

| Log | Models | Repetitions |
|---|---|---|
| `sessions.jsonl` | DeepSeek-V4-flash, GLM-4.5-air, Kimi-K2.6 (main grid); DeepSeek-V4-pro | 3; 1 |
| `sessions_dsf.jsonl`, `sessions_side2.jsonl`, `sessions_dspro.jsonl` | parallel partial runs with session keys that `sessions.jsonl` also holds (it takes precedence) | |
| `sessions_glm53.jsonl`, `sessions_gpt-6-sol.jsonl`, `sessions_claude-opus-5.5.jsonl` | GLM-5.3, GPT-6 (gpt-6-sol), Claude-Opus-5.5 | 1 |
| `sessions_ablate.jsonl` | prompt ablations (DeepSeek-V4-flash, Kimi-K2.6) | 1 |

Files whose name contains `side`, and the partial runs above, come from parallel runs (some walking the grid in reverse
order to finish sooner). A session key `(question, configuration, model, repetition)` can therefore appear in two files; `code/score.py` keeps the first
occurrence, reading `sessions.jsonl` first and the other files in name order. GLM-5.3, GPT-6 and Claude-Opus-5.5 were
called through an OpenAI-compatible gateway whose endpoint and key are read from `LLMHUB_BASE_URL` and
`LLMHUB_API_KEY`. Local paths that some agents printed by listing engine settings are replaced by `/work/...`.

## Data and ethics

TPC-H and TPC-DS are generated with the DuckDB extensions; BIRD `financial` is public. The enterprise domain contains
only synthetic data generated from a fixed seed under a de-identified policy structure; it contains no company data,
identifiers or credentials.

## License

Code: MIT. Generated data and logs: CC BY 4.0.
