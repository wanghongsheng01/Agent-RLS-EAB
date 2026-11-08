"""Application-layer result cache in front of the enforcement point (E9, E9M, E9S).

The cache sits where an MCP server or application reuses tool results: it keys a data-tool result on the tool name
and the request (normalized SQL text for run_sql; the canonical argument object for query_metric, i.e. the query
intent, as in semantic caches for OLAP such as arXiv 2602.19811) and is shared by every principal of a deployment.
E9 caches the results of the rewriting gateway (E3T), E9M those of the governed metric tool (E4); E9S keys the
same cache on the principal as well. Errors are not cached; the declassified KPI tool is not cached (its result is
the same for every principal).

Noninterference for cached sessions: a hit returns the result that the entry's creator obtained under its own
scope, so the replay recomputes that creator's result on the requester's perturbed instances (Definition 2).
"""
import json, os, re, threading, time

from enforce import Executor

CACHE_BASE = {"E9": "E3T", "E9M": "E4", "E9S": "E3T"}
DATA_TOOLS = ("run_sql", "query_metric")


def norm_sql(s):
    return re.sub(r"\s+", " ", (s or "").strip().rstrip(";")).lower()


def cache_key(name, args):
    if name == "run_sql":
        return (name, norm_sql(args.get("sql", "")))
    return (name, json.dumps(args, sort_keys=True, ensure_ascii=False))


def _is_error(out):
    try:
        return isinstance(json.loads(out), dict) and "error" in json.loads(out)
    except Exception:
        return False


class ResultCache:
    """One cache per deployment (domain x model x repetition x configuration stream)."""

    def __init__(self, scoped):
        self.scoped, self.d, self.lock = scoped, {}, threading.Lock()
        self.stats = {"lookups": 0, "hits": 0, "cross_hits": 0, "executions": 0}


class CachedExecutor:
    def __init__(self, ex, cache):
        self.ex, self.cache = ex, cache

    @property
    def releases(self):
        return self.ex.releases

    @property
    def verifier_usage(self):
        return self.ex.verifier_usage

    def tools(self):
        return self.ex.tools()

    def call(self, name, args):
        if name not in DATA_TOOLS:
            return self.ex.call(name, args)
        t0 = time.perf_counter()
        k = cache_key(name, args)
        key = (self.ex.p, k) if self.cache.scoped else k
        with self.cache.lock:
            hit = self.cache.d.get(key)
            self.cache.stats["lookups"] += 1
        if hit is not None:
            out, owner = hit
            # fresh result under the requester's scope, for the analysis only (never returned)
            fresh, _ = self.ex.call(name, args)
            with self.cache.lock:
                self.cache.stats["hits"] += 1
                self.cache.stats["cross_hits"] += owner != self.ex.p
            return out, {"enf_ms": 0.0, "exec_ms": 0.0, "sql": None, "total_ms": (time.perf_counter() - t0) * 1000,
                         "cache_hit": True, "cache_owner": owner, "cache_wrong": _canon(out) != _canon(fresh)}
        out, meta = self.ex.call(name, args)
        with self.cache.lock:
            self.cache.stats["executions"] += 1
            if not _is_error(out):
                self.cache.d.setdefault(key, (out, self.ex.p))
        return out, {**meta, "cache_hit": False, "cache_owner": self.ex.p, "cache_wrong": False}


def _canon(out):
    """Order-insensitive comparison; error messages that echo the executed SQL are cut before the SQL, and perturbed
    schema names are mapped back to main (as in renoni.py / renoni_multi.py)."""
    try:
        d = json.loads(out)
    except Exception:
        return out
    if isinstance(d, dict) and isinstance(d.get("error"), str):
        d["error"] = re.split(r"\n\s*\nLINE \d+:|\nLINE \d+:", d["error"])[0]
    if isinstance(d, dict) and "rows" in d:
        d["rows"] = sorted(json.dumps(r, sort_keys=True) for r in d["rows"])
    return re.sub(r"pert_[a-z]+", "main", json.dumps(d, sort_keys=True))


PERT_FILES = {1: "{n}_pert.duckdb", 2: "{n}_pert2.duckdb", 3: "{n}_pert3.duckdb"}


def _executor(dom, owner, p, cfg, k):
    """Executor of `owner`'s scope reading the requester `p`'s perturbed instance k."""
    ex = Executor(dom, owner, CACHE_BASE[cfg], base="pert")
    ex.path = os.path.join(os.path.dirname(dom.pert), PERT_FILES[k].format(n=dom.name))
    ex.schema = f"pert_{p}"
    ex.filtered = dom.filtered(owner, src=ex.schema)
    return ex


def cache_noninterference(dom, p, cfg, calls):
    """Per perturbation k: list of per-call violations (data tools only). A call returned `out` (its own result or a
    cached one created by `cache_owner`); it violates noninterference if recomputing the same result on p's
    perturbed instance changes it."""
    res = {}
    for k in (1, 2, 3):
        exs = {}
        v = []
        for c in calls:
            if c["name"] not in DATA_TOOLS:
                continue
            owner = c.get("cache_owner", p)
            if owner not in exs:
                exs[owner] = _executor(dom, owner, p, cfg, k)
            o2 = exs[owner].call(c["name"], c["args"])[0]
            v.append(_canon(c["full_out"]) != _canon(o2))
        res[k] = v
    return res
