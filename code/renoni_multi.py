"""Noninterference replay against two further, independent perturbations per principal.

Each variant k rewrites the constants of the original perturbation: amount multipliers and additive offsets change,
a different residue class of forbidden facts is deleted, renamed strings get another suffix and dates another shift.
Every recorded session's tool calls are replayed on the original instance and on variant k.
Writes pilot/ni_pert{k}.json (session key -> violation) for k = 2, 3 (the original perturbation is k = 1).
"""
import json, os, re, sys
from concurrent.futures import ThreadPoolExecutor

import duckdb
import domains, domains2
from domains import DOMAINS
from score import iter_sessions
import agent
from agent import noninterference, make_verifier

_orig = agent._canon


def _canon2(out):
    # same canonicalisation as renoni.py (error messages echo the rewritten SQL, which embeds the schema name)
    try:
        d = json.loads(out)
        if isinstance(d, dict) and isinstance(d.get("error"), str):
            d["error"] = re.split(r"\n\s*\nLINE \d+:|\nLINE \d+:", d["error"])[0]
            out = json.dumps(d)
    except Exception:
        pass
    return re.sub(r"pert_[a-z]+", "main", _orig(out))


agent._canon = _canon2

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def vary(sql, k):
    sql = re.sub(r"\* (1\.\d+)", lambda m: f"* {float(m.group(1)) + 0.1 * k:.2f}", sql)
    sql = re.sub(r"\+ (\d+)(?=\s+(AS|END)\b)", lambda m: f"+ {int(m.group(1)) + k}", sql)
    sql = re.sub(r"% (\d+) <> 0", lambda m: f"% {m.group(1)} <> {k - 1}", sql)
    sql = sql.replace("'-X'", f"'-X{k}'").replace("'#'", f"'#{k}'").replace("'.x'", f"'.x{k}'")
    sql = sql.replace("'00-'", f"'0{k}-'").replace("INTERVAL 40 DAY", f"INTERVAL {40 + 13 * k} DAY")
    return sql


class _Conn:
    def __init__(self, c, k):
        self.c, self.k = c, k

    def execute(self, sql, *a):
        return self.c.execute(vary(sql, self.k), *a)

    def __getattr__(self, n):
        return getattr(self.c, n)


def build(dom, k):
    dom.pert = os.path.join(os.path.dirname(dom.pert), f"{dom.name}_pert{k}.duckdb")
    if not os.path.exists(dom.pert):
        real = duckdb.connect
        conn = lambda path, *a, **kw: _Conn(real(path, *a, **kw), k)  # noqa: E731
        domains.duckdb.connect = domains2.duckdb.connect = conn
        try:
            dom.build_pert()
        finally:
            domains.duckdb.connect = domains2.duckdb.connect = real


def main(k):
    doms = {n: c() for n, c in DOMAINS.items()}
    for d in doms.values():
        build(d, k)
    path = os.path.join(HERE, "pilot", f"ni_pert{k}.json")
    out = json.load(open(path)) if os.path.exists(path) else {}
    todo = [(f"{s['qid']}|{s['cfg']}|{s['model']}|{s['rep']}", s)
            for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl"))
            if f"{s['qid']}|{s['cfg']}|{s['model']}|{s['rep']}" not in out]
    print(k, len(todo), "sessions to replay", flush=True)

    def work(ks):
        key, s = ks
        dom, p = s["qid"].split("-")[:2]
        calls = [{"name": c["name"], "args": c["args"]} for c in s["calls"]]
        ver = make_verifier(doms[dom], p, s["model"], s["rep"]) if s["cfg"] == "E2" else None
        return key, any(noninterference(doms[dom], p, "E3T" if s["cfg"] == "E5" else s["cfg"], calls, verifier=ver))

    n = 0
    with ThreadPoolExecutor(8) as ex:
        for key, v in ex.map(work, todo):
            out[key] = v
            n += 1
            if n % 2000 == 0:
                json.dump(out, open(path, "w"))
                print(k, n, flush=True)
    json.dump(out, open(path, "w"))
    print(k, "done", len(out), sum(out.values()), flush=True)


if __name__ == "__main__":
    for k in map(int, sys.argv[1:] or ["2", "3"]):
        main(k)
