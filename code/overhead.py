"""Enforcement-mechanism overhead, isolated from the LLM: replay every distinct SQL query the agents issued under E3T
through raw execution (no enforcement), E3T (gateway rewrite), E5 (in-database secure views) and E3N (non-Truman
double execution); 5 timed runs each after one warm-up, single-threaded DuckDB."""
import json, os, statistics, time
from domains import DOMAINS
from enforce import Executor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
doms = {k: v() for k, v in DOMAINS.items()}
from score import iter_sessions
qs = {}
for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
    if s["cfg"] != "E3T":
        continue
    dom, p = s["qid"].split("-")[:2]
    for c in s["calls"]:
        if c["name"] == "run_sql" and c["args"].get("sql"):
            qs[(dom, p, c["args"]["sql"])] = 1
print(len(qs), "distinct queries")
res = {c: [] for c in ("E0", "E3T", "E5", "E3N")}
for (dom, p, sql) in qs:
    row = {}
    for cfg in res:
        ex = Executor(doms[dom], p, cfg)
        ex.call("run_sql", {"sql": sql})
        ts = []
        for _ in range(5):
            t = time.perf_counter(); out, _m = ex.call("run_sql", {"sql": sql}); ts.append((time.perf_counter() - t) * 1000)
        row[cfg] = statistics.median(ts)
    if all(v < 20000 for v in row.values()):
        for cfg in res:
            res[cfg].append(row[cfg])
out = {}
for cfg, v in res.items():
    v = sorted(v)
    out[cfg] = {"n": len(v), "median_ms": round(statistics.median(v), 2), "p95_ms": round(v[int(0.95 * len(v)) - 1], 2),
                "mean_ms": round(sum(v) / len(v), 2)}
base = res["E0"]
for cfg in ("E3T", "E5", "E3N"):
    ratios = sorted(a / b for a, b in zip(res[cfg], base) if b > 0)
    out[cfg]["median_ratio_vs_raw"] = round(statistics.median(ratios), 2)
    out[cfg]["p95_ratio_vs_raw"] = round(ratios[int(0.95 * len(ratios)) - 1], 2)
json.dump(out, open(os.path.join(HERE, "pilot", "overhead.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
