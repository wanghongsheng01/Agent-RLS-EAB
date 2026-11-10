"""Bounds beyond Definition 3 (RQ3): for every session of the session auditor (E7, E8) that released published
aggregates, the interval of each protected cell, per released period, that is consistent with the releases, the
visible cells and nonnegativity of the atom totals (linear programs, HiGHS). Reports the share of sessions in which
some protected cell is pinned to an interval narrower than 10% of its value. Writes pilot/lp_bounds.json."""
import json, os
from collections import defaultdict

import numpy as np
from scipy.optimize import linprog

from domains import DOMAINS
from enforce import _cell_index, _release_vec, kpi_atoms

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = ("ds-flash", "glm-air", "kimi-k2.6")
_PROJ = {}
FAILED = [0]


def releases(d, s):
    out = []
    for c in s["calls"]:
        if c["name"] != "company_kpi" or '"value"' not in c["out"]:
            continue
        parsed, err = d.kpi_parse(c["args"])
        if not err:
            out.append(parsed)
    return out


def widths(d, p, rels, atoms):
    cells, periods, idx = _cell_index(d, p)
    vis = set(d.visible_cells(p))
    inv = {i: k for k, i in idx.items()}
    if d.name == "ent":  # projected cells of the production model: sum the atoms they cover
        if (p, "proj") not in _PROJ:
            agg = defaultdict(lambda: defaultdict(float))
            for k, v in atoms.items():
                for mm, x in v.items():
                    agg[(d.project(p, k[:3]), k[3])][mm] += float(x or 0)
            _PROJ[(p, "proj")] = agg
        proj = _PROJ[(p, "proj")]
    def val(i, m):
        c, t = inv[i]
        if d.name == "ent":
            return proj.get((c, t), {}).get(m, 0.0)
        return float(atoms.get((c, t), {}).get(m, 0) or 0)
    res = []
    for m in {r[2] for r in rels}:
        R = [r for r in rels if r[2] == m]
        tp = sorted({t for r in R for t in r[1]})
        cols = [i for (c, t), i in idx.items() if t in tp]
        x0 = np.array([val(i, m) for i in cols])
        x0 = x0 / max(1.0, float(np.abs(x0).max()))  # scale for conditioning; reported widths are ratios
        A = [ _release_vec(d, p, r, idx)[cols] for r in R]
        b = [a @ x0 for a in A]
        bounds = [(x0[j], x0[j]) if inv[i][0] in vis else (0, None) for j, i in enumerate(cols)]
        for s in d.secret_cells(p):
            for t in tp:
                j = cols.index(idx[(s, t)])
                if x0[j] <= 0:
                    continue
                c = np.zeros(len(cols)); c[j] = 1
                lo = linprog(c, A_eq=np.array(A), b_eq=b, bounds=bounds, method="highs")
                hi = linprog(-c, A_eq=np.array(A), b_eq=b, bounds=bounds, method="highs")
                if lo.status != 0 or hi.status not in (0, 3):  # solver failure (numerical); counted, not used
                    FAILED[0] += 1
                    continue
                up = float("inf") if hi.status == 3 else -hi.fun
                res.append((lo.fun / x0[j], up / x0[j]))
    return res


def main():
    doms = {k: DOMAINS[k]() for k in ("tpch", "tpcds", "bird", "ent")}
    atoms = {k: kpi_atoms(d, "main") for k, d in doms.items()}
    agg = defaultdict(lambda: {"sessions": 0, "tight10": 0, "prule10": 0, "widths": [], "ups": []})
    for l in open(os.path.join(HERE, "pilot", "sessions.jsonl")):
        s = json.loads(l)
        if s["cfg"] not in ("E7", "E8") or s["model"] not in MODELS:
            continue
        dom, p = s["qid"].split("-")[:2]
        d = doms[dom]
        if not d.secret_cells(p):
            continue
        rels = releases(d, s)
        if not rels:
            continue
        w = widths(d, p, rels, atoms[dom])
        for k in (dom, "all"):
            a = agg[k]; a["sessions"] += 1
            a["tight10"] += any(h - l < 0.10 for l, h in w)
            a["prule10"] += any(h <= 1.10 or l >= 0.90 for l, h in w)  # an estimate within 10% from one side
            a["widths"] += [h - l for l, h in w]; a["ups"] += [h for l, h in w]
    # whole histories of the auditor-state experiment (run_audit.py): union of a principal's releases in one stream
    import glob
    hist = defaultdict(list)
    for fn in glob.glob(os.path.join(HERE, "pilot", "auditstate", "E7P*_*.jsonl")):
        cfg, model, dom, rep = os.path.basename(fn)[:-6].split("_")
        for l in open(fn):
            x = json.loads(l)
            hist[(cfg, model, dom, rep, x["qid"].split("-")[1])] += [(r[0], r[1], r[2]) for r in x.get("releases", [])]
    for (cfg, model, dom, rep, p), rels in hist.items():
        d = doms[dom]
        if not d.secret_cells(p) or not rels:
            continue
        w = widths(d, p, rels, atoms[dom])
        for k in (f"hist|{cfg}", f"hist|{cfg}|{dom}"):
            a = agg[k]; a["sessions"] += 1
            a["tight10"] += any(h - l < 0.10 for l, h in w)
            a["prule10"] += any(h <= 1.10 or l >= 0.90 for l, h in w)
            a["widths"] += [h - l for l, h in w]; a["ups"] += [h for l, h in w]
    out = {k: {"sessions": a["sessions"], "tight10": round(100 * a["tight10"] / a["sessions"], 1),
               "median_rel_width": round(float(np.median(a["widths"])), 2) if a["widths"] else None,
               "min_rel_width": round(float(min(a["widths"])), 3) if a["widths"] else None,
               "prule10": round(100 * a["prule10"] / a["sessions"], 2),
               "min_rel_upper": round(float(min(a["ups"])), 3) if a["ups"] else None}
           for k, a in agg.items()}
    out["solver_failures"] = FAILED[0]
    json.dump(out, open(os.path.join(HERE, "pilot", "lp_bounds.json"), "w"), indent=1)
    print(out)


if __name__ == "__main__":
    main()
