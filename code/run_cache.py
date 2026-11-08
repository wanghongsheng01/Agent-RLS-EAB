"""Run the application-layer cache configurations (E9, E9M, E9S).

A cache is shared by all principals of one deployment, so the sessions of one stream (domain x model x repetition x
configuration) run sequentially in a fixed order: the domain's questions shuffled with seed (domain, repetition),
the same order for every model and configuration. Streams run in parallel. A stream is rerun from the start unless
its file is complete (LLM responses are cached, so a rerun repeats the same trajectories at no cost).
Writes pilot/appcache/<cfg>_<model>_<dom>_r<rep>.jsonl and pilot/appcache/stats*.json.
"""
import argparse, json, os, random, threading, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import llm
from domains import DOMAINS
from agent import run_session
from appcache import ResultCache

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "pilot", "appcache")

ap = argparse.ArgumentParser()
ap.add_argument("--models", default="ds-flash,glm-air,kimi-k2.6")
ap.add_argument("--configs", default="E9,E9M,E9S")
ap.add_argument("--doms", default="tpch,tpcds,bird,ent")
ap.add_argument("--reps", default="0,1,2")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--workers", type=int, default=8, help="parallel streams per model")
ap.add_argument("--stats", default="stats.json", help="cache statistics file (one per concurrent run)")
a = ap.parse_args()
os.makedirs(OUT, exist_ok=True)
suite = json.load(open(os.path.join(HERE, "pilot", "suite.json")))
doms = {k: DOMAINS[k]() for k in a.doms.split(",")}
lock = threading.Lock()
stats_path = os.path.join(OUT, a.stats)
STATS = json.load(open(stats_path)) if os.path.exists(stats_path) else {}


def order(dom, rep):
    items = [x for x in suite if x["dom"] == dom]
    random.Random(f"{dom}-{rep}").shuffle(items)
    return items[:a.limit] if a.limit else items


def stream(cfg, model, dom, rep):
    items = order(dom, rep)
    fn = os.path.join(OUT, f"{cfg}_{model}_{dom}_r{rep}.jsonl")
    if os.path.exists(fn) and sum(1 for _ in open(fn)) == len(items):
        return fn, 0
    cache = ResultCache(scoped=(cfg == "E9S"))
    rows = []
    for i, it in enumerate(items):
        r = run_session(doms[dom], it, cfg, model, rep=rep, cache=cache)
        r["order"] = i
        rows.append(r)
    with open(fn, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    with lock:
        STATS[os.path.basename(fn)] = cache.stats
        json.dump(STATS, open(stats_path, "w"), indent=1)
    return fn, len(rows)


jobs = [(c, m, d, int(r)) for m in a.models.split(",") for r in a.reps.split(",") for d in a.doms.split(",")
        for c in a.configs.split(",")]
pools = {m: ThreadPoolExecutor(a.workers) for m in a.models.split(",")}
futs = {pools[j[1]].submit(stream, *j): j for j in jobs}
print(len(jobs), "streams", flush=True)
n = 0
for f in as_completed(futs):
    n += 1
    try:
        fn, k = f.result()
        print(n, os.path.basename(fn), k, {m: round(v, 2) for m, v in llm.spent_today().items()}, flush=True)
    except Exception:
        print("ERR", futs[f], traceback.format_exc()[-600:], flush=True)
