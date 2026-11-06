"""Recompute the inference-leakage verdict of every recorded session from its released aggregates (after fixing the
BIRD cell universe, which wrongly contained an ungrouped cell). Writes pilot/secrecy_recomputed.json."""
import json, os
from domains import DOMAINS
from enforce import determined
from score import iter_sessions

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
doms = {k: v() for k, v in DOMAINS.items()}
out = {}
for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
    dom, p = s["qid"].split("-")[:2]
    d = doms[dom]
    rel = []
    for c in s["calls"]:
        if c["name"] == "company_kpi" and not c["out"].startswith('{"error"'):
            parsed, err = d.kpi_parse(c["args"])
            if parsed:
                rel.append(parsed)
    out[f"{s['qid']}|{s['cfg']}|{s['model']}|{s['rep']}"] = bool(determined(d, p, rel))
json.dump(out, open(os.path.join(HERE, "pilot", "secrecy_recomputed.json"), "w"))
print(len(out), sum(out.values()))
