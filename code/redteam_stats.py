"""Statistics of the adaptive red team (redteam.py): per configuration, the share of attacks that obtained the
protected value (any agent answer, the attacker's own estimate, or determination by the union of releases), and each
route separately. Writes pilot/redteam_stats.json."""
import glob, json, os
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    acc = defaultdict(lambda: defaultdict(int))
    for fn in glob.glob(os.path.join(HERE, "pilot", "redteam2", "*.jsonl")):
        for l in open(fn):
            r = json.loads(l)
            for k in (r["cfg"], f"{r['cfg']}|{r['agent']}"):
                a = acc[k]
                a["n"] += 1; a["sessions"] += len(r["turns"])
                for f in ("success", "answer_hit", "estimate_hit", "determined", "read_outside"):
                    a[f] += bool(r[f])
    out = {k: {"n": a["n"], "sessions": a["sessions"],
               **{f: round(100 * a[f] / a["n"], 4) for f in ("success", "answer_hit", "estimate_hit", "determined", "read_outside")}}
           for k, a in acc.items()}
    json.dump(out, open(os.path.join(HERE, "pilot", "redteam_stats.json"), "w"), indent=1)
    for k, v in sorted(out.items()):
        print(k, v)


if __name__ == "__main__":
    main()
