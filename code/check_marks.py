"""Check that marking best/second values changed no number: strip \\textbf{}, \\underline{} and the B/S column from the
marked tables and compare their data rows with those of a reference copy (default: the Overleaf repository)."""
import os, re, sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REF = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "overleaf_git")


def rows(fn):
    out = []
    for l in open(fn):
        l = l.rstrip()
        if " & " not in l or not l.endswith("\\\\") or l.startswith(" & ") or "Config." in l or "Benign acc." in l:
            continue
        l = re.sub(r"\\textbf\{([^}]*)\}", r"\1", l)
        l = re.sub(r"\\underline\{([^}]*)\}", r"\1", l)
        cells = re.sub(r"\s*&\s*$", "", l[:-2].rstrip()).split(" & ")
        out.append(cells)
    return out


bad = 0
for t in ("tab_main.tex", "tab_dom.tex", "tab_model.tex", "tab_ablate.tex"):
    new, old = rows(os.path.join(HERE, "paper", t)), rows(os.path.join(REF, t))
    oldm = {c[0]: c[1:] for c in old}
    for c in new:
        o = oldm.get(c[0])
        if o is None:
            continue
        n = c[1:len(o) + 1]
        if n != o:
            bad += 1
            print("DIFF", t, c[0], n, o)
    print(t, "rows checked:", sum(1 for c in new if c[0] in oldm))
print("numbers unchanged" if bad == 0 else f"{bad} differing rows")
