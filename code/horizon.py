"""Long-horizon replay of the published channel (LLM-free): for each principal, the published-figure requests that
agents issued without auditing (E3T streams of run_audit.py, three models x three repetitions) are concatenated into
histories of 1, 3, or 9 streams in random order and replayed against the per-principal auditor (E7P: deny a release
that, with the earlier granted ones, determines a protected functional) and the two static safe subsets (E7Z
finest-first, E7Zc coarsest-first). Reports the share of requests denied. Writes pilot/horizon.json."""
import glob, json, os, random
from collections import defaultdict

from domains import DOMAINS
from enforce import safe_scopes
from audit_incr import IncrementalAuditor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    doms = {k: DOMAINS[k]() for k in ("tpch", "tpcds", "bird", "ent")}
    streams = defaultdict(list)  # (dom, p) -> list of request lists (one per stream)
    for fn in sorted(glob.glob(os.path.join(HERE, "pilot", "auditstate", "E3T_*.jsonl"))):
        dom = os.path.basename(fn).split("_")[2]
        per = defaultdict(list)
        for l in open(fn):
            s = json.loads(l)
            p = s["qid"].split("-")[1]
            for c in s["calls"]:
                if c["name"] == "company_kpi":
                    parsed, err = doms[dom].kpi_parse(c["args"])
                    if not err:
                        per[p].append(parsed)
        for p, rs in per.items():
            streams[(dom, p)].append(rs)
    out = {}
    for h in (1, 3, 9):
        tot = defaultdict(lambda: [0, 0])
        for (dom, p), ss in streams.items():
            d = doms[dom]
            if not d.secret_cells(p):
                continue
            for seed in range(3 if h < 9 else 1):
                rng = random.Random(f"{dom}-{p}-{h}-{seed}")
                pick = rng.sample(ss, h) if h < len(ss) else list(ss)
                rng.shuffle(pick)
                reqs = [r for st in pick for r in st]
                A = IncrementalAuditor(d, p)
                for r in reqs:
                    bad = bool(A.check(r))
                    if not bad:
                        A.add(r)
                    tot["E7P"][0] += bad; tot["E7P"][1] += 1
                    for name, cf in (("E7Z", False), ("E7Zc", True)):
                        tot[name][0] += r[0] not in safe_scopes(d, p, coarse_first=cf); tot[name][1] += 1
        out[h] = {k: {"denied": round(100 * a / n, 2), "requests": n} for k, (a, n) in tot.items()}
        print(h, out[h], flush=True)
    json.dump(out, open(os.path.join(HERE, "pilot", "horizon.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
