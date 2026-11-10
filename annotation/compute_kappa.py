"""Cohen's kappa between two annotators and between each annotator and the automatic judge.
Usage: python compute_kappa.py annotator_A.csv annotator_B.csv   (copies of annotation_sheet.csv with label_yes_no filled)"""
import csv, sys
from collections import Counter


def labels(fn):
    return {r["item"]: (r["task"], r["label_yes_no"].strip().lower()) for r in csv.DictReader(open(fn))}


def kappa(a, b):
    keys = [k for k in a if k in b and a[k] in ("yes", "no") and b[k] in ("yes", "no")]
    n = len(keys)
    po = sum(a[k] == b[k] for k in keys) / n
    ca, cb = Counter(a[k] for k in keys), Counter(b[k] for k in keys)
    pe = sum(ca[x] * cb[x] for x in ("yes", "no")) / n / n
    return n, po, (po - pe) / (1 - pe) if pe < 1 else 1.0


key = {r["item"]: (r["task"], r["judge_label"]) for r in csv.DictReader(open("judge_key.csv"))}
anns = [labels(f) for f in sys.argv[1:]]
for task in ("leak", "misleading"):
    J = {k: v for k, (t, v) in key.items() if t == task}
    A = [{k: v for k, (t, v) in x.items() if t == task} for x in anns]
    for i, a in enumerate(A):
        n, po, k = kappa(a, J)
        print(f"{task}: annotator {i + 1} vs judge: n={n} agreement={po:.3f} kappa={k:.3f}")
    if len(A) == 2:
        n, po, k = kappa(A[0], A[1])
        print(f"{task}: annotator 1 vs 2: n={n} agreement={po:.3f} kappa={k:.3f}")
