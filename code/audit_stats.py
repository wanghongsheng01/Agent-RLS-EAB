"""Statistics of the auditor-state experiment (run_audit.py): per configuration, the share of principal histories
(one principal's sessions in one stream) whose union of releases determines a protected functional (Definition 3
applied to the history), session-level differencing, and utility. Writes pilot/audit_stats.json."""
import glob, json, os
from collections import defaultdict

from domains import DOMAINS
from enforce import determined
from score import judge

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pct(k, n):
    return round(100 * k / n, 4) if n else None


def main():
    doms = {k: DOMAINS[k]() for k in ("tpch", "tpcds", "bird", "ent")}
    hist = defaultdict(list)
    acc = defaultdict(lambda: defaultdict(int))
    for fn in glob.glob(os.path.join(HERE, "pilot", "auditstate", "*.jsonl")):
        cfg, model, dom, rep = os.path.basename(fn)[:-6].split("_")
        for l in open(fn):
            s = json.loads(l)
            p = s["qid"].split("-")[1]
            hist[(cfg, model, dom, rep, p)] += [tuple((r[0], tuple(r[1]), r[2])) for r in s["releases"]]
            r = judge(s)
            denied = sum('AuditDenied' in c["out"] for c in s["calls"] if c["name"] == "company_kpi")
            for key in ((cfg, "all"), (cfg, dom)):
                a = acc[key]
                a["sessions"] += 1
                c = r["cat"]
                if c in ("B1", "B3"):
                    a["benign"] += 1; a["correct"] += bool(r["correct"]); a["ben_denied"] += denied > 0
                if c == "B2":
                    a["b2"] += 1; a["mis"] += bool(r["misleading"])
                if c in ("A3", "C1"):
                    a[c] += 1; a[c + "_det"] += bool(s["secrecy"]); a[c + "_leak"] += bool(r["leak"])
                if c in ("C2", "C3"):
                    a[c] += 1; a[c + "_ok"] += bool(r["correct"])
    for (cfg, model, dom, rep, p), rels in hist.items():
        d = doms[dom]
        if not d.secret_cells(p):
            continue
        det = bool(determined(d, p, [(x, list(t), m) for x, t, m in rels])) if rels else False
        for key in ((cfg, "all"), (cfg, dom)):
            acc[key]["hist"] += 1; acc[key]["hist_det"] += det
    out = {}
    for (cfg, k), a in sorted(acc.items()):
        out[f"{cfg}|{k}"] = {"sessions": a["sessions"], "hist": a["hist"], "hist_det": pct(a["hist_det"], a["hist"]),
                             "acc": pct(a["correct"], a["benign"]), "ben_denied": pct(a["ben_denied"], a["benign"]),
                             "mis": pct(a["mis"], a["b2"]), "a3_det": pct(a["A3_det"], a["A3"]),
                             "a3_leak": pct(a["A3_leak"], a["A3"]), "c1_det": pct(a["C1_det"], a["C1"]),
                             "c1_leak": pct(a["C1_leak"], a["C1"]), "c2_ok": pct(a["C2_ok"], a["C2"]),
                             "c3_ok": pct(a["C3_ok"], a["C3"]), "n_c3": a["C3"]}
    json.dump(out, open(os.path.join(HERE, "pilot", "audit_stats.json"), "w"), indent=1)
    for k, v in out.items():
        if k.endswith("|all") or "tpch" in k or "bird" in k:
            print(k, v)


if __name__ == "__main__":
    main()
