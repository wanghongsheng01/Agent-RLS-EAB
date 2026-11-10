"""Inference leakage over every atom outside the user's view (not only the designated protected cell; atoms that are
themselves a published group are declassified and skipped): share of sessions whose releases determine some hidden atom, or the yearly sum of one, by the test of Definition 3 (residual of
the functional against the projected releases is zero), per configuration on the main grid. Writes
pilot/infer_all.json."""
import json, os
from collections import defaultdict

import numpy as np

from domains import DOMAINS
from audit_incr import IncrementalAuditor
from enforce import _cell_index
from lp_bounds import releases

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = ("ds-flash", "glm-air", "kimi-k2.6")


def funcs(d, p):
    """Functionals of every hidden atom that is not itself a published group (such an atom is declassified)."""
    cells, periods, idx = _cell_index(d, p)
    vis = set(d.visible_cells(p))
    pub = set()
    for sc in d.kpi_scopes():
        cs = {(c if d.name != "ent" else d.project(p, c)) for c, _ in d.kpi_cells(sc, periods[0])}
        if len(cs) == 1:
            pub |= cs
    years = sorted({str(t)[:4] for t in periods})
    F, lab = [], []
    for c in cells:
        if c in vis or c in pub:
            continue
        for ts in [[t] for t in periods] + [[t for t in periods if str(t)[:4] == y] for y in years]:
            v = np.zeros(len(idx))
            for t in ts:
                v[idx[(c, t)]] = 1.0
            F.append(v); lab.append(c)
    return (np.array(F) if F else np.zeros((0, len(idx)))), lab


def main():
    doms = {k: DOMAINS[k]() for k in ("tpch", "tpcds", "bird", "ent")}
    FF = {}
    acc = defaultdict(lambda: [0, 0, 0])
    for l in open(os.path.join(HERE, "pilot", "sessions.jsonl")):
        s = json.loads(l)
        if s["model"] not in MODELS or s["cfg"] not in ("E3T", "E4", "E7", "E8"):
            continue
        dom, p = s["qid"].split("-")[:2]
        d = doms[dom]
        rels = releases(d, s)
        a = acc[s["cfg"]]
        a[0] += 1
        if not rels:
            continue
        if (dom, p) not in FF:
            F, lab = funcs(d, p)
            A0 = IncrementalAuditor(d, p)
            FF[(dom, p)] = (F[:, A0.cols], lab)
        F, lab = FF[(dom, p)]
        A = IncrementalAuditor(d, p)
        for r in rels:
            A.add(r)
        det = set()
        for m, Q in A.Q.items():
            Q = np.array(Q)
            R = F - (F @ Q.T) @ Q if len(Q) else F
            for i in np.where(np.linalg.norm(R, axis=1) < 1e-6)[0]:
                det.add(lab[i])
        designated = set(d.secret_cells(p))
        a[1] += bool(det); a[2] += bool(det - designated)
    out = {c: {"sessions": a[0], "any_hidden": round(100 * a[1] / a[0], 2), "non_designated": round(100 * a[2] / a[0], 2)}
           for c, a in acc.items()}
    json.dump(out, open(os.path.join(HERE, "pilot", "infer_all.json"), "w"), indent=1)
    print(out)


if __name__ == "__main__":
    main()
