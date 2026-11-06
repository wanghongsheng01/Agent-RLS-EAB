"""Run the pilot grid: items x configs x models (x reps), in parallel, appending one JSON line per session."""
import argparse, json, os, sys, threading, traceback
from concurrent.futures import ThreadPoolExecutor, as_completed

import llm
from domains import DOMAINS
from agent import run_session

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

ap = argparse.ArgumentParser()
ap.add_argument("--models", default="ds-flash,glm-air,kimi-k2.6")
ap.add_argument("--configs", default="E0,E6,E3T,E3N,E4,E4M,E7")
ap.add_argument("--doms", default="tpch,ent")
ap.add_argument("--limit", type=int, default=0)
ap.add_argument("--rep", type=int, default=0)
ap.add_argument("--workers", type=int, default=8)
ap.add_argument("--out", default=os.path.join(HERE, "pilot", "sessions.jsonl"))
a = ap.parse_args()

items = [x for x in json.load(open(os.path.join(HERE, "pilot", "suite.json"))) if x["dom"] in a.doms.split(",")]
if a.limit:
    items = items[:a.limit]
doms = {k: DOMAINS[k]() for k in a.doms.split(",")}
done = set()
if os.path.exists(a.out):
    for l in open(a.out):
        d = json.loads(l)
        done.add((d["qid"], d["cfg"], d["model"], d["rep"]))
jobs = [(it, c, m) for m in a.models.split(",") for c in a.configs.split(",") for it in items
        if (it["qid"], c, m, a.rep) not in done]
if "side" in os.path.basename(a.out):
    jobs.reverse()  # side runs start from the other end of the grid, so they complement the main run
print(len(jobs), "sessions to run", flush=True)
lock = threading.Lock()


def work(job):
    it, c, m = job
    try:
        r = run_session(doms[it["dom"]], it, c, m, rep=a.rep)
    except Exception as e:
        return {"err": repr(e)[:300], "qid": it["qid"], "cfg": c, "model": m, "tb": traceback.format_exc()[-800:]}
    with lock:
        with open(a.out, "a") as f:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")
    return r


# one pool per model so that slow vendors do not starve fast ones
pools = {m: ThreadPoolExecutor(a.workers) for m in a.models.split(",")}
futs = [pools[j[2]].submit(work, j) for j in jobs]
n, errs = 0, 0
for f in as_completed(futs):
    r = f.result(); n += 1
    if "err" in r:
        errs += 1
        print("ERR", r["qid"], r["cfg"], r["model"], r["err"], r.get("tb", "")[-300:], flush=True)
    if n % 50 == 0:
        print(n, "done", errs, "errors", {k: round(v, 2) for k, v in llm.spent_today().items()}, flush=True)
print("finished", n, errs, {k: round(v, 2) for k, v in llm.spent_today().items()})
