"""Incremental auditor (audit_incr.py): agreement with the rank test of enforce.determined on random release
sequences (60 releases per principal and seed, three seeds, every principal with a protected cell), and decision time
per release (median over the 100 releases before 100, 1,000, and, on the production policy model, 10,000
accumulated releases), and the
size of the basis, which never exceeds the number of hidden atoms per metric. Writes pilot/audit_scaling.json (times depend on the
machine; the paper reports the released file)."""
import json, os, random, time

from domains import DOMAINS
from enforce import determined
from audit_incr import IncrementalAuditor

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    mism = checks = 0
    for dn in ("tpch", "tpcds", "bird", "ent"):
        d = DOMAINS[dn]()
        for p in [q for q in d.P if d.secret_cells(q)]:
            scopes, pers = d.kpi_scopes(), (d.years if dn != "ent" else d.MONTHS)
            for seed in range(3):
                rng, A, rel = random.Random(seed), IncrementalAuditor(d, p), []
                for _ in range(60):
                    s = rng.choice(scopes)
                    per = ([rng.choice(pers)] if dn != "ent" or rng.random() < .8 else
                           [m for m in pers if m.startswith(rng.choice(["2025", "2026"]))])
                    r = (s, per, d.KPI_METRICS[rng.random() < .5])
                    a, b = bool(determined(d, p, rel + [r])), bool(A.check(r))
                    checks += 1; mism += a != b
                    if not a:
                        rel.append(r); A.add(r)
    out = {}
    for dn in ("tpch", "bird", "ent"):
        d = DOMAINS[dn](); p = [q for q in d.P if d.secret_cells(q)][0]
        scopes, pers = d.kpi_scopes(), (d.years if dn != "ent" else d.MONTHS)
        rng, A, times, win = random.Random(1), IncrementalAuditor(d, p), {}, []
        n = 10000 if dn == "ent" else 1000
        for i in range(1, n + 1):
            r = (rng.choice(scopes), [rng.choice(pers)], d.KPI_METRICS[rng.random() < .5])
            t = time.perf_counter(); bad = A.check(r); dt = (time.perf_counter() - t) * 1000
            if not bad:
                A.add(r)
            win = (win + [dt])[-100:]
            if i in (100, 1000, 10000):  # median decision time over the last 100 releases
                times[i] = round(sorted(win)[len(win) // 2], 2)
        times["basis_rows"] = sum(len(q) for q in A.Q.values())
        times["hidden_atoms"] = int(len(A.cols))
        out[dn] = times
    json.dump({"mismatches": mism, "checks": checks, "per_release_ms": out},
              open(os.path.join(HERE, "pilot", "audit_scaling.json"), "w"), indent=1)
    print(mism, checks, out)


if __name__ == "__main__":
    main()
