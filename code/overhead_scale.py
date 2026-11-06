"""Mechanism overhead at larger TPC-H scale factors: replay every distinct TPC-H query the agents issued under E3T
through raw execution (E0), gateway rewriting (E3T), secure views (E5) and the non-Truman check (E3N) on TPC-H
generated at SF 1 and SF 5 (same nations, so the same policies apply). 3 timed runs after one warm-up.
Usage: overhead_scale.py WORKDIR [SF ...]; writes pilot/overhead_scale.json. WORKDIR holds the generated databases.
"""
import json, os, statistics, sys, time

import duckdb
import enforce
from domains import TPCH
from enforce import Executor
from score import iter_sessions

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def instance(work, sf):
    db = os.path.join(work, f"tpch_sf{sf}.duckdb")
    if not os.path.exists(db):
        c = duckdb.connect(db)
        c.execute("INSTALL tpch; LOAD tpch")
        c.execute(f"CALL dbgen(sf={sf})")
        c.close()
    d = TPCH()
    d.db = d.pert = db  # E5 attaches d.pert as 'base'; only its main schema is used here
    cat = os.path.join(work, f"e5_sf{sf}")  # one catalog directory per scale factor (connections are cached by path)
    os.makedirs(cat, exist_ok=True)
    for p in d.P:
        e5 = os.path.join(cat, f"e5_tpch_{p}.duckdb")
        if os.path.exists(e5):
            continue
        c = duckdb.connect(e5)
        c.execute(f"ATTACH '{db}' AS base (READ_ONLY)")
        c.execute("CREATE SCHEMA m")
        filt = d.filtered(p, src="base.main")
        for (t,) in c.execute("SELECT table_name FROM duckdb_tables() WHERE database_name='base'").fetchall():
            c.execute(f"CREATE VIEW m.{t} AS {filt.get(t, f'SELECT * FROM base.main.{t}')}")
        c.close()
    enforce.PILOT = cat  # E5 looks up its catalog here
    return d


def main(work, sfs):
    qs = {}
    for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
        if s["cfg"] == "E3T" and s["qid"].startswith("tpch-"):
            for c in s["calls"]:
                if c["name"] == "run_sql" and c["args"].get("sql"):
                    qs[(s["qid"].split("-")[1], c["args"]["sql"])] = 1
    out = {"queries": len(qs)}
    for sf in sfs:
        d = instance(work, sf)
        res = {c: [] for c in ("E0", "E3T", "E5", "E3N")}
        for p, sql in qs:
            row = {}
            for cfg in res:
                ex = Executor(d, p, cfg)
                ex.call("run_sql", {"sql": sql})
                ts = []
                for _ in range(3):
                    t = time.perf_counter(); ex.call("run_sql", {"sql": sql}); ts.append((time.perf_counter() - t) * 1000)
                row[cfg] = statistics.median(ts)
            if all(v < 20000 for v in row.values()):
                for cfg in res:
                    res[cfg].append(row[cfg])
        o = {}
        for cfg, v in res.items():
            v = sorted(v)
            o[cfg] = {"n": len(v), "median_ms": round(statistics.median(v), 2), "p95_ms": round(v[int(0.95 * len(v)) - 1], 2)}
        out[f"sf{sf}"] = o
        print(sf, o, flush=True)
        json.dump(out, open(os.path.join(HERE, "pilot", "overhead_scale.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1], [float(x) if "." in x else int(x) for x in sys.argv[2:] or ["0.05", "1", "5"]])
