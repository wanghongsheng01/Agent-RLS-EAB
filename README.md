# Agent-RLS Bench

Reproduction package for *[Experiment, Analysis, and Benchmark] Where Should Row- and Column-Level Permissions Be
Enforced for LLM Data Agents?*

The benchmark compares nine enforcement configurations for LLM data agents that answer questions through multi-step
tool calls over governed relational data, and an application-layer result cache in front of two of them. It measures answer leakage, trace noninterference, inference leakage
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
| `code/appcache.py`, `code/run_cache.py`, `code/cache_stats.py` | Application-layer result cache (E9: shared, keyed on the SQL text, over E3T; E9M: shared, keyed on the metric request, over E4; E9S: keyed on the principal as well), its sequential stream driver, and its statistics |
| `code/suite_x7.py`, `code/run_audit.py`, `code/audit_stats.py` | Split complement questions C3; streams of each domain's sessions per model and repetition for E3T, the per-session auditor E7, the per-principal auditor E7P, E7P with the isolation rule (E7PR), and the static safe subsets E7Z (finest first) and E7Zc (coarsest first; E7Z' in the paper); history-level statistics |
| `code/horizon.py` | LLM-free replay of the published-figure requests over long histories: denial rates of E7P, E7Z and E7Zc |
| `code/redteam.py`, `code/redteam_stats.py` | Adaptive red team: an attacker LLM (DeepSeek-V4-pro) opens up to six sessions with the agent and adapts to the answers; success by answer, own estimate, or determination by the union of releases |
| `code/native_rls_more.py` | Loads TPC-DS and BIRD into the embedded PostgreSQL server with row policies and column grants (E5P on all four domains) |
| `code/make_kappa_pack.py`, `annotation/` | Human audit of the automatic judge: 150 stratified sessions, annotation sheet, judge key, `compute_kappa.py` |
| `code/check_marks.py` | Checks that marking best/second values in the tables changed no number |
| `code/infer_all.py` | Inference leakage with every hidden atom (not itself a published group) treated as protected |
| `code/audit_incr.py`, `code/audit_scaling.py` | Incremental auditor (Proposition 1), its agreement with the rank test and its time per release |
| `code/cache_designs.py` | LLM-free replay of scope-keyed, per-user and below-gateway caches with 1, 3 or 9 users per role |
| `code/lp_bounds.py` | Intervals of protected cells under nonnegativity in auditor sessions (needs the databases; result in `logs/lp_bounds.json.gz`) |
| `code/run_*.sh` | Run scripts for every experiment |
| `paper_tools/` | Scripts that generate every number, table and figure of the paper |
| `data/suite.json`, `data/suite_x6.json`, `data/suite_x7.json` | The 169 questions with ground truth; the 15 follow-up questions C1 (complement differencing) and C2 (own group total); the 12 split complement questions C3 |
| `logs/sessions*.jsonl.gz` | Every agent session: tool calls, arguments, responses, final answers, tokens, cost, latency |
| `logs/appcache.tar.gz` | Sessions of the cache configurations, one file per stream (configuration, model, domain, repetition), and cache statistics |
| `logs/redteam.tar.gz` | Red-team attacks, one file per configuration, agent and attempt |
| `logs/auditstate.tar.gz` | Sessions of the auditor-state experiment (E3T, E7, E7P, E7PR, E7Z, E7Zc), one file per stream, with the releases of every session |
| `logs/llm_cache.tar.gz` | Cached LLM responses: re-running the experiments reproduces all sessions without API calls |
| `scripts/` | Database preparation |

## Reproduce the paper's numbers (no API key needed)

```bash
pip install -r requirements.txt
python scripts/prepare_bird.py /path/to/bird/dev_databases/financial/financial.sqlite
python scripts/build_dbs.py
mkdir -p pilot && for f in logs/*.jsonl.gz logs/*.json.gz; do gunzip -c $f > pilot/$(basename ${f%.gz}); done
cp data/suite*.json pilot/ && tar -xzf logs/appcache.tar.gz -C pilot && tar -xzf logs/auditstate.tar.gz -C pilot && tar -xzf logs/redteam.tar.gz -C pilot
python paper_tools/make_numbers.py && python paper_tools/make_figs.py && python paper_tools/make_fig_cache.py
```

To re-run the agents from the cache, extract `logs/llm_cache.tar.gz` into the package root and run
`code/run_grid.sh` (and `code/run_cache.py` and `code/run_audit.py` for the cache and auditor-state configurations, whose
sessions run sequentially per stream in a fixed shuffled order). Every LLM request is served from the cache. To run new models, set `LLM_KEYS_JSON` to a JSON file
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
| `sessions_more_reps.jsonl` | GLM-5.3 and DeepSeek-V4-pro, repetitions 2 and 3 of the same core configurations | 2 |
| `sessions_external.jsonl` | E2X and E6X: GPT-6 as verifier and output guard of the DeepSeek-V4-flash and Kimi-K2.6 agents | 1 |
| `sessions_e3d.jsonl` | E3D, the data-independent non-Truman check (static scope implication plus rewrite), main grid | 3 |
| `appcache/E9*_<model>_<domain>_r<rep>.jsonl` | E9, E9M and E9S, main grid (3 repetitions); E9 and E9M for DeepSeek-V4-pro, GLM-5.3, GPT-6 and Claude-Opus-5.5; E9 for GPT-6.1, Kimi-K3 and Kimi-K3.1-Pro | 3; 1 |
| `auditstate/<cfg>_<model>_<domain>_r<rep>.jsonl` | E3T, E7, E7P, E7PR, E7Z and E7Zc on all questions including C1--C3, one shuffled stream per model and repetition, main grid | 3 |
| `sessions_e5p.jsonl` | E5P, PostgreSQL 16 row-level security in the agent loop on all four domains (DeepSeek-V4-flash and GLM-4.5-air; Kimi-K2.6 on TPC-H and the production policy model); needs the databases built by `code/native_rls.py` and `code/native_rls_more.py` | 3 |
| `sessions_e8s.jsonl` | E8S, the recommended E8 with the user's scope stated in the prompt (DeepSeek-V4-flash, GLM-4.5-air; Kimi-K2.6 served through the organization's gateway) | 3 |
| `sessions_newest.jsonl` | GPT-6.1 (gpt-6.1-sol), Kimi-K3 (gateway) and Kimi-K3.1-Pro (`kimi-k3-1-pro-261024`, Volcano Ark): E0, E3T, E4M, E7 and E8 on all questions | 1 |
| `kimi_channel_check.jsonl` | Kimi-K2.6 E0/E3T sessions (TPC-H, BIRD, repetition 0) re-run through the organization's gateway; `code/kimi_channel_check.py` compares them with the vendor API | 1 |

Files whose name contains `side`, and the partial runs above, come from parallel runs (some walking the grid in reverse
order to finish sooner). A session key `(question, configuration, model, repetition)` can therefore appear in two files; `code/score.py` keeps the first
occurrence, reading `sessions.jsonl` first and the other files in name order. GLM-5.3, GPT-6 and Claude-Opus-5.5 were
called through an OpenAI-compatible gateway whose endpoint and key are read from `LLMHUB_BASE_URL` and
`LLMHUB_API_KEY`. The Kimi vendor account was suspended on 2026-11-10; Kimi-K2.6 sessions that `sessions_e8s.jsonl` and
`sessions_e5p.jsonl` (BIRD, TPC-DS) hold were run through the organization's gateway, which `code/kimi_channel_check.py`
found not equivalent to the vendor API (outcome agreement 81% against 93% between two vendor repetitions; attack leakage
9.5% vs. 34.5%). `paper_tools/make_numbers.py` therefore keeps them as a separate deployment, `kimi-k2.6-gw`: they are
never pooled with vendor-API Kimi-K2.6 sessions, the gateway-served E0/E3T sessions form the "Kimi (gw)" column of
Table VII, and the paired E8S comparison uses the models with a complete vendor-API grid (DeepSeek-V4-flash, GLM-4.5-air).
Kimi-K3.1-Pro is called on Volcano Ark (`ARK_BASE_URL`, `ARK_API_KEY`; temperature 1.0, the only value the endpoint
accepts). `code/with_keys.sh` shows how the run scripts take every key from the environment. Local paths that some agents printed by listing engine settings are replaced by `/work/...`.

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
