"""Incremental session/principal auditor (Proposition 1): the visible atoms are projected out once, and an orthonormal
basis of the released rows (per metric) is updated with one Gram-Schmidt step per release; a protected functional is
determined iff it has no residual against the basis. Decisions equal enforce.determined (checked by
audit_check.py on random and logged release sequences); the cost per release is O(r |A_hidden|) for r basis rows."""
import numpy as np

from enforce import _cell_index, _release_vec

EPS = 1e-9


class IncrementalAuditor:
    def __init__(self, d, p):
        self.d, self.p = d, p
        cells, periods, self.idx = _cell_index(d, p)
        vis = set(d.visible_cells(p))
        self.cols = np.array([i for (c, t), i in self.idx.items() if c not in vis])  # hidden atoms only
        years = sorted({str(t)[:4] for t in periods})
        self.funcs = []
        for s in d.secret_cells(p):
            for lab, ts in [(str(t), [t]) for t in periods] + [(y, [t for t in periods if str(t)[:4] == y]) for y in years]:
                v = np.zeros(len(self.idx))
                for t in ts:
                    v[self.idx[(s, t)]] = 1.0
                self.funcs.append(((s, lab), v[self.cols]))
        self.Q = {}  # metric -> list of orthonormal rows

    def _residual(self, Q, v):
        for q in Q:
            v = v - (q @ v) * q
        return v

    def check(self, rel):
        """Protected functionals determined if `rel` were released on top of the current state."""
        Q = list(self.Q.get(rel[2], []))
        w = self._residual(Q, _release_vec(self.d, self.p, rel, self.idx)[self.cols])
        if np.linalg.norm(w) > EPS:
            Q.append(w / np.linalg.norm(w))
        return [(rel[2], s, lab) for (s, lab), c in self.funcs if np.linalg.norm(self._residual(Q, c)) < 1e-6]

    def add(self, rel):
        Q = self.Q.setdefault(rel[2], [])
        w = self._residual(Q, _release_vec(self.d, self.p, rel, self.idx)[self.cols])
        if np.linalg.norm(w) > EPS:
            Q.append(w / np.linalg.norm(w))


def isolated(d, p, releases):
    """Stricter, still data-independent rule (E7PR): a protected functional counts as disclosed if it is determined
    once any single further hidden atom is known, i.e. if its residual against the releases is parallel to the
    residual of one hidden atom. This covers a cell that the releases pin down together with one other hidden atom,
    whose value nonnegativity then bounds from above. With the projector P = I - Q^T Q onto the complement of the
    releases, the residual of atom h is P e_h, and r_c = P c is parallel to it iff r_c[h]^2 = |r_c|^2 P[h, h]."""
    A = IncrementalAuditor(d, p)
    for r in releases:
        A.add(r)
    n = len(A.cols)
    Q = np.array(A.Q.get(releases[-1][2], [])) if releases else np.zeros((0, n))
    P = np.eye(n) - (Q.T @ Q if len(Q) else 0)
    diag = np.diag(P)
    out = []
    for (s, lab), c in A.funcs:
        rc = P @ c
        nc = rc @ rc
        if nc < 1e-12:
            out.append((s, lab)); continue
        ok = (c == 0) & (diag > 1e-9) & (np.abs(rc ** 2 - nc * diag) <= 1e-6 * np.maximum(1.0, nc * diag))
        if ok.any():
            out.append((s, lab))
    return out
