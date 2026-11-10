"""Statistics of the application-layer cache configurations (E9, E9M, E9S) against their base configurations
(E3T, E4) on the same models and repetitions. Writes pilot/appcache_stats.json; all cache numbers in the paper
come from this file (paper/tools/make_numbers.py reads it)."""
import glob, json, os
from collections import defaultdict

from score import judge, load, SUITE

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = {"E9": "E3T", "E9M": "E4", "E9S": "E3T"}
MODELS = ("ds-flash", "glm-air", "kimi-k2.6")
DOMS = ("tpch", "tpcds", "bird", "ent")


def _shared():
    """Questions whose wording another principal of the same domain also asks (the cache can serve them across
    principals by text alone); the rest are reused only when the agents' own statements coincide."""
    texts = defaultdict(set)
    for q in SUITE.values():
        if not q["cat"].startswith("C"):
            texts[(q["dom"], q["text"])].add(q["p"])
    return {q["qid"]: len(texts[(q["dom"], q["text"])]) > 1 for q in SUITE.values() if not q["cat"].startswith("C")}


def sessions():
    for fn in sorted(glob.glob(os.path.join(HERE, "pilot", "appcache", "E9*.jsonl"))):
        for l in open(fn):
            yield json.loads(l)


def pct(k, n):
    return round(100 * k / n, 4) if n else None


def main():
    acc = defaultdict(lambda: defaultdict(int))
    shared = _shared()
    for s in sessions():
        r = judge(s)
        keys = ((s["cfg"], "all"), (s["cfg"], r["dom"]),
                (s["cfg"], "shared" if shared[s["qid"]] else "unshared")) if s["model"] in MODELS else ()  # main grid
        for key in keys + ((s["cfg"], s["model"]),):
            a = acc[key]
            a["sessions"] += 1
            data = [c for c in s["calls"] if c["name"] in ("run_sql", "query_metric")]
            a["data_calls"] += len(data)
            a["hits"] += sum(bool(c.get("cache_hit")) for c in data)
            a["cross_hits"] += sum(bool(c.get("cache_hit")) and c.get("cache_owner") != s["qid"].split("-")[1]
                                   for c in data)  # noqa: E501
            a["wrong"] += sum(bool(c.get("cache_wrong")) for c in data)
            # over-privileged: answered from another principal's entry and dependent on data outside the requester's
            # view (Definition 2 on all three perturbations); violations of calls that the cache did not serve from
            # another principal are the tied-row artifacts of the base configuration (RQ1) and are not counted
            p = s["qid"].split("-")[1]
            op = [bool(v) and bool(c.get("cache_hit")) and c.get("cache_owner") != p
                  for c, v in zip(data, s.get("ni_per_call", []))]
            a["overpriv"] += sum(op)
            a["ni_sessions"] += any(op)
            a["sess_wrong"] += any(c.get("cache_wrong") for c in data)
            if r["cat"] in ("B1", "B3"):
                a["benign"] += 1; a["correct"] += bool(r["correct"])
            if r["cat"] == "B2":
                a["b2"] += 1; a["misleading"] += bool(r["misleading"])
            if r["cat"].startswith("A"):
                a["attack"] += 1; a["leak"] += bool(r["leak"])
            if r["cat"] in ("A1", "A2"):
                a["direct"] += 1; a["leak_direct"] += bool(r["leak"])
    # base configurations on the same models and repetitions (main sessions)
    rows = [r for r in load(os.path.join(HERE, "pilot", "sessions.jsonl"))
            if r["cfg"] in ("E3T", "E4") and not r["cat"].startswith("C")
            and (r["model"] in MODELS or r["rep"] == 0)]
    for r in rows:
        keys = ((r["cfg"], "all"), (r["cfg"], r["dom"])) if r["model"] in MODELS else ()
        for key in keys + ((r["cfg"], r["model"]),):
            a = acc[key]
            a["sessions"] += 1; a["ni_sessions"] += bool(r["ni"])
            if r["cat"] in ("B1", "B3"):
                a["benign"] += 1; a["correct"] += bool(r["correct"])
            if r["cat"] == "B2":
                a["b2"] += 1; a["misleading"] += bool(r["misleading"])
            if r["cat"].startswith("A"):
                a["attack"] += 1; a["leak"] += bool(r["leak"])
            if r["cat"] in ("A1", "A2"):
                a["direct"] += 1; a["leak_direct"] += bool(r["leak"])
    stats = {}
    for fn in glob.glob(os.path.join(HERE, "pilot", "appcache", "stats*.json")):
        stats.update(json.load(open(fn)))
    ex = defaultdict(lambda: [0, 0])
    for fn, st in stats.items():
        cfg, model, dom, _rep = fn[:-6].split("_")
        for k in (("all", dom) if model in MODELS else ()) + (model,):
            ex[(cfg, k)][0] += st["executions"]; ex[(cfg, k)][1] += st["lookups"]
    out = {}
    for (cfg, k), a in sorted(acc.items()):
        o = {"sessions": a["sessions"], "data_calls": a.get("data_calls"),
             "hit": pct(a["hits"], a["data_calls"]), "cross_hit": pct(a["cross_hits"], a["data_calls"]),
             "wrong": pct(a["wrong"], a["data_calls"]), "overpriv": pct(a["overpriv"], a["data_calls"]),
             "overpriv_of_cross": pct(a["overpriv"], a["cross_hits"]) if a.get("cross_hits") else None,
             "sess_wrong": pct(a["sess_wrong"], a["sessions"]),
             "ni": pct(a["ni_sessions"], a["sessions"]), "acc": pct(a["correct"], a["benign"]),
             "mislead": pct(a["misleading"], a["b2"]), "leak": pct(a["leak"], a["attack"]),
             "leak_direct": pct(a["leak_direct"], a["direct"]),
             "n_benign": a["benign"], "n_attack": a["attack"]}
        if (cfg, k) in ex:
            e, lk = ex[(cfg, k)]
            o["executions"], o["lookups"], o["exec_saved"] = e, lk, pct(lk - e, lk)
        out[f"{cfg}|{k}"] = o
    json.dump(out, open(os.path.join(HERE, "pilot", "appcache_stats.json"), "w"), indent=1)
    for k, o in out.items():
        if True:
            print(k, {x: o.get(x) for x in ("sessions", "data_calls", "hit", "cross_hit", "wrong", "overpriv", "ni",
                                             "acc", "mislead", "leak", "leak_direct", "exec_saved")})


if __name__ == "__main__":
    main()
