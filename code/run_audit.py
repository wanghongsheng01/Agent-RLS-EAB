"""Auditor state across sessions (E7P) and a static safe subset of the published channel (E7Z), against E3T and the
per-session auditor E7.

A principal can open many sessions. The sessions of one stream (domain x model x repetition x configuration) run
sequentially in a fixed order (the domain's questions of suite.json, suite_x6.json and suite_x7.json shuffled with
seed (domain, repetition)), as consecutive sessions of the domain's principals. E7P keeps the auditor's releases per
principal across the stream; E7 starts every session empty; E7Z withholds a precomputed scope set; every session logs
its releases, so the union over a principal's sessions can be tested with Definition 3. Streams run in parallel.
Writes pilot/auditstate/<cfg>_<model>_<dom>_r<rep>.jsonl.
"""
import argparse, json, os, random, threading, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import llm
from domains import DOMAINS
from agent import run_session

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "pilot", "auditstate")

ap = argparse.ArgumentParser()
ap.add_argument("--models", default="ds-flash,glm-air,kimi-k2.6")
ap.add_argument("--configs", default="E3T,E7,E7P,E7Z")
ap.add_argument("--doms", default="tpch,tpcds,bird,ent")
ap.add_argument("--reps", default="0,1,2")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--workers", type=int, default=8, help="parallel streams per model")
a = ap.parse_args()
os.makedirs(OUT, exist_ok=True)
suite = []
for f in ("suite.json", "suite_x6.json", "suite_x7.json"):
    suite += json.load(open(os.path.join(HERE, "pilot", f)))
doms = {k: DOMAINS[k]() for k in a.doms.split(",")}


def order(dom, rep):
    items = [x for x in suite if x["dom"] == dom]
    random.Random(f"audit-{dom}-{rep}").shuffle(items)
    return items[:a.limit] if a.limit else items


def stream(cfg, model, dom, rep):
    items = order(dom, rep)
    fn = os.path.join(OUT, f"{cfg}_{model}_{dom}_r{rep}.jsonl")
    if os.path.exists(fn) and sum(1 for _ in open(fn)) == len(items):
        return fn, 0
    state, rows = {}, []
    for i, it in enumerate(items):
        r = run_session(doms[dom], it, cfg, model, rep=rep, audit_state=state)
        r["order"] = i
        rows.append(r)
    with open(fn, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
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
