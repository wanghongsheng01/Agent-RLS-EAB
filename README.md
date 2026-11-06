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
| `code/renoni_multi.py` | Noninterference replay against two further, independent perturbations per principal |
| `code/native_rls.py` | E5 with native PostgreSQL 16 row-level security (embedded via `pgserver`): probes and overhead |
| `code/overhead_scale.py` | Overhead replay on TPC-H at SF 0.05, 1 and 5 |
| `code/suite_x6.py` | Generator of the follow-up questions C1 and C2 |
| `code/run_*.sh` | Run scripts for every experiment |
| `paper_tools/` | Scripts that generate every number, table and figure of the paper |
| `data/suite.json`, `data/suite_x6.json` | The 169 questions with ground truth; the 15 follow-up questions C1 (complement differencing) and C2 (own group total) |
| `logs/sessions*.jsonl.gz` | Every agent session: tool calls, arguments, responses, final answers, tokens, cost, latency |
| `logs/llm_cache.tar.gz` | Cached LLM responses: re-running the experiments reproduces all sessions without API calls |
| `scripts/` | Database preparation |

## Reproduce the paper's numbers (no API key needed)

```bash
pip install -r requirements.txt
python scripts/prepare_bird.py /path/to/bird/dev_databases/financial/financial.sqlite
python scripts/build_dbs.py
mkdir -p pilot && for f in logs/*.jsonl.gz logs/*.json.gz; do gunzip -c $f > pilot/$(basename ${f%.gz}); done
cp data/suite*.json pilot/
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
| `sessions_ablate.jsonl`, `sessions_x1.jsonl` | prompt ablations E3T+P, E3N+P, E4M+H and E4M+T (DeepSeek-V4-flash, Kimi-K2.6) | 1 |
| `sessions_x2.jsonl` | E8 with a reworded coverage note (E8P), main grid | 3 |
| `sessions_x6.jsonl`, `sessions_x6s.jsonl`, `sessions_x6f.jsonl` | follow-up C1/C2 questions under E3T, E7, E7S (static own-group rule) and E8, and E7S on the A3/B3 questions; main grid, and GPT-6 and Claude-Opus-5.5 | 3; 1 |
| `sessions_frontier_reps.jsonl` | GPT-6 and Claude-Opus-5.5, repetitions 2 and 3 of E0, E3T, E4M, E7, E8 on the attack, scope-ambiguous and published-channel questions | 2 |

Files whose name contains `side`, and the partial runs above, come from parallel runs (some walking the grid in reverse
order to finish sooner). A session key `(question, configuration, model, repetition)` can therefore appear in two files; `code/score.py` keeps the first
occurrence, reading `sessions.jsonl` first and the other files in name order. GLM-5.3, GPT-6 and Claude-Opus-5.5 were
called through an OpenAI-compatible gateway whose endpoint and key are read from `LLMHUB_BASE_URL` and
`LLMHUB_API_KEY`. Local paths that some agents printed by listing engine settings are replaced by `/work/...`.

## Changelog of the harness before the final runs

Two harness defects were found by independent review and fixed before the runs reported in the paper; all affected
sessions were re-run and all derived metrics recomputed, so every number in the paper comes from the fixed harness.

1. The agent-facing database file also contained the perturbed copies used by the noninterference replay. Sessions of
   E3T, E7 and E4M reached them in 9 sessions by listing the catalog. The agent-facing file now contains only the
   original instance, the gateway rejects references to other schemas and catalogs, and the affected sessions were re-run.
2. The published national total of BIRD contained an ungrouped cell, which hid one multi-release reconstruction from
   the auditor. The cell universe was fixed, the 127 affected audited sessions were re-run, and inference leakage was
   recomputed for all sessions.

## Data and ethics

TPC-H and TPC-DS are generated with the DuckDB extensions; BIRD `financial` is public. The enterprise domain contains
only synthetic data generated from a fixed seed under a de-identified policy structure; it contains no company data,
identifiers or credentials.

## License

Code: MIT. Generated data and logs: CC BY 4.0.
