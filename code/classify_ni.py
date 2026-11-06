"""Classify the replay differences of Truman configurations (which cannot read data outside the view by construction):
'environment' = the call inspects the session environment (database/schema names, catalog listings), which differs
between the original and the replay file; 'selection' = the visible rows returned under truncation or LIMIT differ
among tied or unordered rows (same columns, every returned row is visible). Writes pilot/ni_truman_classes.json."""
import json, os, re
from domains import DOMAINS
from enforce import Executor
from score import iter_sessions
import agent

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENV = re.compile(r"current_(database|schema|catalog|role|user)|duckdb_\w+\(|information_schema|pg_catalog|sqlite_master", re.I)
ni = json.load(open(os.path.join(HERE, "pilot", "ni_recomputed.json")))
doms = {k: v() for k, v in DOMAINS.items()}


def canon(o):
    try:
        d = json.loads(o)
        if isinstance(d, dict) and isinstance(d.get("error"), str):
            d["error"] = re.split(r"\n\s*\nLINE \d+:|\nLINE \d+:", d["error"])[0]
            o = json.dumps(d)
    except Exception:
        pass
    return re.sub(r"pert_[a-z]+", "main", agent._canon(o))


out = {}
for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
    k = f"{s['qid']}|{s['cfg']}|{s['model']}|{s['rep']}"
    if s["cfg"] not in ("E3T", "E4", "E7", "E8") or not ni.get(k):
        continue
    d, p = doms[s["qid"].split("-")[0]], s["qid"].split("-")[1]
    a, b = Executor(d, p, s["cfg"]), Executor(d, p, s["cfg"], base="pert")
    cls = "other"
    for c in s["calls"]:
        o1, o2 = a.call(c["name"], c["args"])[0], b.call(c["name"], c["args"])[0]
        if c["name"] == "company_kpi" or canon(o1) == canon(o2):
            continue
        if ENV.search(json.dumps(c["args"])):
            cls = "environment"
        else:
            j1, j2 = json.loads(o1), json.loads(o2)
            if "error" not in j1 and "error" not in j2 and j1.get("columns") == j2.get("columns") and \
                    (j1.get("truncated") or j2.get("truncated") or "limit" in json.dumps(c["args"]).lower()
                     or c["name"] == "query_metric"):
                cls = "selection"
        break
    out[k] = cls
json.dump(out, open(os.path.join(HERE, "pilot", "ni_truman_classes.json"), "w"), indent=1)
from collections import Counter
print(Counter(out.values()))
