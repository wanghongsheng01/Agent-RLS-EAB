"""Recompute the noninterference verdict of every recorded session (after fixing two harness artefacts found in the
pilot: the perturbed ENT tables had a different physical row order, so LIMIT without ORDER BY picked different visible
rows; and current_schema() exposed the harness schema name). Writes pilot/ni_recomputed.json."""
import json, os, re
from domains import DOMAINS
from score import iter_sessions
from agent import noninterference, _canon, make_verifier
import agent
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_orig = agent._canon


def _canon2(out):
    # error messages echo the rewritten SQL (which embeds the instance's schema name); keep only the message head
    try:
        d = json.loads(out)
        if isinstance(d, dict) and isinstance(d.get("error"), str):
            d["error"] = re.split(r"\n\s*\nLINE \d+:|\nLINE \d+:", d["error"])[0]
            out = json.dumps(d)
    except Exception:
        pass
    return re.sub(r"pert_[a-z]+", "main", _orig(out))


agent._canon = _canon2
doms = {k: v() for k, v in DOMAINS.items()}
path = os.path.join(HERE, "pilot", "ni_recomputed.json")
out = json.load(open(path)) if os.path.exists(path) and "--all" not in os.sys.argv else {}
todo = []
for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
    k = f"{s['qid']}|{s['cfg']}|{s['model']}|{s['rep']}"
    if k not in out:
        todo.append((k, s))


def work(ks):
    k, s = ks
    dom, p = s["qid"].split("-")[:2]
    calls = [{"name": c["name"], "args": c["args"]} for c in s["calls"]]
    ver = make_verifier(doms[dom], p, s["model"], s["rep"]) if s["cfg"] == "E2" else None
    return k, any(noninterference(doms[dom], p, "E3T" if s["cfg"] == "E5" else s["cfg"], calls, verifier=ver))


with ThreadPoolExecutor(8) as ex:
    for k, v in ex.map(work, todo):
        out[k] = v
json.dump(out, open(path, "w"))
print(len(out), sum(out.values()), "new", len(todo))
