"""E5 with native row-level security: PostgreSQL 16 (embedded via pgserver) instead of secure views emulated in DuckDB.

Each principal is a role with column-level SELECT grants (hidden columns are not granted) and a row policy
(CREATE POLICY ... USING <row predicate>) on every protected table. The original instance and each principal's
perturbed twin live in separate databases with identical policies, as in the DuckDB experiments.
Re-runs the LLM-free probes of mechanism.py (noninterference, existence inference, binary-search side channel) and
the overhead replay of overhead.py (TPC-H and production-policy queries, owner vs. role). Writes pilot/native_rls.json.
"""
import json, os, re, statistics, sys, time

import duckdb, psycopg, sqlglot
import pgserver
from domains import TPCH, ENT
from score import iter_sessions
from agent import _canon
import mechanism

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PGDATA = os.environ.get("AGENT_RLS_PGDATA", os.path.join(HERE, "pilot", "pgdata"))
TMP = os.path.join(PGDATA + "_csv")
TYPES = [(r"^TINYINT|^UTINYINT", "SMALLINT"), (r"^UBIGINT|^HUGEINT", "NUMERIC"), (r"^UINTEGER", "BIGINT"),
         (r"^USMALLINT", "INTEGER"), (r"^DOUBLE", "DOUBLE PRECISION"), (r"^FLOAT", "REAL")]
PROTECTED = {"tpch": ["customer", "orders", "lineitem"], "ent": ["ads_sales_m", "dws_export_order", "dim_customer"]}


def pgtype(t):
    for pat, r in TYPES:
        if re.match(pat, t):
            return r
    return t


def row_predicates(d, p):
    if hasattr(d, "row_preds"):  # TPC-DS and BIRD: the same predicates as the gateway rewrite, on schema main
        return {t: pr for t, pr in d.row_preds(p, "main").items() if pr}
    if d.name == "tpch":
        k = d.vis_keys(p)
        cust = f"SELECT c_custkey FROM main.customer WHERE c_nationkey IN {k}"
        return {"customer": f"c_nationkey IN {k}", "orders": f"o_custkey IN ({cust})",
                "lineitem": f"l_orderkey IN (SELECT o_orderkey FROM main.orders WHERE o_custkey IN ({cust}))"}
    cl = "(" + ", ".join(f"'{c}'" for c in d.custs[p]) + ")"
    return {"ads_sales_m": d.P[p]["ads"], "dws_export_order": f"customer_code IN {cl}",
            "dim_customer": f"customer_code IN {cl}"}


def load(admin_uri, d, dbname, src_file, src_schema, principals):
    """Copy every table of src_schema into database dbname (schema main) and install roles, grants and policies."""
    with psycopg.connect(admin_uri, autocommit=True) as a:
        if a.execute("SELECT 1 FROM pg_database WHERE datname=%s", (dbname,)).fetchone():
            return
        a.execute(f"CREATE DATABASE {dbname}")
    os.makedirs(TMP, exist_ok=True)
    src = duckdb.connect(src_file, read_only=True)
    tabs = [r[0] for r in src.execute(f"SELECT table_name FROM duckdb_tables() WHERE schema_name='{src_schema}'").fetchall()]
    uri = admin_uri.replace("/postgres?", f"/{dbname}?")
    with psycopg.connect(uri, autocommit=True) as c:
        c.execute("CREATE SCHEMA main")
        c.execute("CREATE FUNCTION main.error(msg text) RETURNS integer LANGUAGE plpgsql AS "
                  "$$ BEGIN RAISE EXCEPTION '%', msg; END $$")
        for t in tabs:
            cols = src.execute(f"DESCRIBE {src_schema}.{t}").fetchall()
            c.execute(f"CREATE TABLE main.{t} (" + ", ".join(f'"{n}" {pgtype(ty)}' for n, ty, *_ in cols) + ")")
            f = os.path.join(TMP, f"{dbname}_{t}.csv")
            src.execute(f"COPY (SELECT * FROM {src_schema}.{t}) TO '{f}' (HEADER, DELIMITER ',')")
            c.execute(f"COPY main.{t} FROM '{f}' WITH (FORMAT csv, HEADER true)")
            os.remove(f)
        c.execute("ANALYZE")
        for p in principals:
            role = f"r_{d.name}_{p}"
            if not c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone():
                c.execute(f"CREATE ROLE {role}")
            c.execute(f"GRANT USAGE ON SCHEMA main TO {role}")
            hid = d.hidden(p)
            for t in tabs:
                cols = [r[0] for r in src.execute(f"DESCRIBE {src_schema}.{t}").fetchall()]
                vis = [x for x in cols if x not in hid]
                c.execute(f"GRANT SELECT ({', '.join(vis)}) ON main.{t} TO {role}" if len(vis) < len(cols)
                          else f"GRANT SELECT ON main.{t} TO {role}")
            for t, pred in row_predicates(d, p).items():
                c.execute(f"ALTER TABLE main.{t} ENABLE ROW LEVEL SECURITY")
                c.execute(f"CREATE POLICY pol_{p} ON main.{t} FOR SELECT TO {role} USING ({pred})")


class Native:
    """run_sql against the native-RLS database of one principal (base 'main' = original, 'pert' = twin)."""

    def __init__(self, admin_uri, d, p, base="main", as_owner=False):
        db = f"{d.name}_orig" if base == "main" else f"{d.name}_pert_{p}"
        self.c = psycopg.connect(admin_uri.replace("/postgres?", f"/{db}?"), autocommit=True)
        self.c.execute("SET search_path TO main; SET statement_timeout = '20s'")
        if not as_owner:
            self.c.execute(f"SET ROLE r_{d.name}_{p}")

    def run(self, sql):
        q = translate(sql)
        if q is None:
            return json.dumps({"error": "not translatable"})
        try:
            cur = self.c.execute(q)
            cols = [x.name for x in cur.description] if cur.description else []
            rows = [[float(v) if isinstance(v, (int, float)) or type(v).__name__ == "Decimal" else
                     (None if v is None else str(v)) for v in r] for r in cur.fetchmany(50)]
            return json.dumps({"columns": cols, "rows": rows})
        except Exception as e:
            return json.dumps({"error": type(e).__name__ + ": " + str(e).split("\n")[0]})


def translate(sql):
    if "duckdb_tables()" in sql:  # catalog statistics probe: the PostgreSQL counterpart is pg_class.reltuples
        t = re.search(r"table_name\s*=\s*'(\w+)'", sql)
        return f"SELECT relname, reltuples FROM pg_class WHERE relname = '{t.group(1)}'" if t else None
    try:
        return sqlglot.transpile(sql, read="duckdb", write="postgres")[0]
    except Exception:
        return None


def probes(admin, d, p, key, plist):
    out = {}
    for name, sql in plist:
        a, b = Native(admin, d, p).run(sql), Native(admin, d, p, base="pert").run(sql)
        out[name] = {"ni_leak": _canon(a) != _canon(b), "out": a[:200]}
    return out


def existence(admin, d, p, n=120):
    ex = Native(admin, d, p)
    c = duckdb.connect(d.db, read_only=True)
    if d.name == "tpch":
        rows = c.execute(f"""SELECT c_custkey, COUNT(o_orderkey) > 0 FROM customer LEFT JOIN orders ON o_custkey=c_custkey
            AND year(o_orderdate)=1997 WHERE c_nationkey NOT IN {d.vis_keys(p)} GROUP BY 1 ORDER BY 1 LIMIT {n}""").fetchall()
        q = lambda k: f"SELECT COUNT(*) FROM orders WHERE o_custkey = {k} AND year(o_orderdate) = 1997"  # noqa: E731
    else:
        ks = c.execute(f"""SELECT customer_code FROM dim_customer WHERE customer_code NOT IN {tuple(d.custs[p])}
            ORDER BY 1 LIMIT {n}""").fetchall()
        rows = [(k, c.execute(f"SELECT COUNT(*) > 0 FROM dws_export_order WHERE customer_code='{k}' AND order_month "
                              f"LIKE '2026-0%'").fetchone()[0]) for (k,) in ks]
        q = lambda k: f"SELECT COUNT(*) FROM dws_export_order WHERE customer_code = '{k}' AND order_month LIKE '2026-0%'"  # noqa: E731

    def guess(o):
        j = json.loads(o)
        return True if "error" in j else j["rows"][0][0] > 0
    resp = [(ex.run(q(k)), h) for k, h in rows]
    acc = sum(guess(o) == h for o, h in resp) / len(resp)
    base = max(sum(h for _, h in resp), len(resp) - sum(h for _, h in resp)) / len(resp)
    return acc, base


def binsearch(admin, d, p, key):
    inner = (f"(SELECT SUM(o_totalprice) FROM orders WHERE o_custkey = {key})" if d.name == "tpch" else
             f"(SELECT SUM(amount) FROM dws_export_order WHERE customer_code = '{key}')")
    ex = Native(admin, d, p)
    lo, hi, n = 0.0, 1e8, 0
    while hi - lo > 0.01 and n < 60:
        mid = (lo + hi) / 2
        o = ex.run(f"SELECT CASE WHEN {inner} > {mid} THEN error('big') ELSE 0 END AS r")
        n += 1
        lo, hi = (mid, hi) if "big" in o else (lo, mid)
    return round((lo + hi) / 2, 2), n


def overhead(admin, doms):
    qs = {}
    for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
        dom = s["qid"].split("-")[0]
        if s["cfg"] == "E3T" and dom in doms:
            for c in s["calls"]:
                if c["name"] == "run_sql" and c["args"].get("sql"):
                    qs[(dom, s["qid"].split("-")[1], c["args"]["sql"])] = 1
    conns, res, n_ok = {}, {"owner": [], "rls": []}, 0
    for dom, p, sql in qs:
        for mode in ("owner", "rls"):
            if (dom, p, mode) not in conns:
                conns[(dom, p, mode)] = Native(admin, doms[dom], p, as_owner=(mode == "owner"))
        row = {}
        for mode in ("owner", "rls"):
            ex = conns[(dom, p, mode)]
            if "error" in json.loads(ex.run(sql)):
                row[mode] = None
                continue
            ts = []
            for _ in range(5):
                t = time.perf_counter(); ex.run(sql); ts.append((time.perf_counter() - t) * 1000)
            row[mode] = statistics.median(ts)
        if row["owner"] is not None and row["rls"] is not None:
            n_ok += 1
            res["owner"].append(row["owner"]); res["rls"].append(row["rls"])
    out = {"queries": len(qs), "executed_both": n_ok}
    for m, v in res.items():
        v = sorted(v)
        out[m] = {"median_ms": round(statistics.median(v), 2), "p95_ms": round(v[int(0.95 * len(v)) - 1], 2)}
    r = sorted(a / b for a, b in zip(res["rls"], res["owner"]) if b > 0)
    out["median_ratio_rls_vs_owner"] = round(statistics.median(r), 2)
    return out


if __name__ == "__main__":
    srv = pgserver.get_server(PGDATA, cleanup_mode=None)
    admin = srv.get_uri()
    res = {}
    doms = {}
    for D, p0 in ((TPCH, "eu"), (ENT, "pb")):
        d = D(); doms[d.name] = d
        load(admin, d, f"{d.name}_orig", d.db, "main", list(d.P))
        for p in d.P:
            load(admin, d, f"{d.name}_pert_{p}", d.pert, f"pert_{p}", [p])
        key, plist = mechanism.probes_tpch(d) if D is TPCH else mechanism.probes_ent(d)
        res[d.name] = {"probes": probes(admin, d, p0, key, plist), "existence": existence(admin, d, p0),
                       "binsearch": binsearch(admin, d, p0, key)}
        print(d.name, json.dumps(res[d.name], indent=1)[:3000], flush=True)
    if "--no-overhead" not in sys.argv:
        res["overhead"] = overhead(admin, doms)
        print(res["overhead"])
    json.dump(res, open(os.path.join(HERE, "pilot", "native_rls.json"), "w"), indent=1)
