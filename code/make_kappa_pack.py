"""Human audit of the automatic judge: a stratified sample of 150 main-grid sessions (75 attack sessions judged for
answer leakage, 75 scope-ambiguous sessions judged for Truman-misleading answers), written as an annotation sheet
without the judge's labels, plus a separate key and compute_kappa.py. Writes annotation/."""
import csv, json, os, random
from collections import defaultdict

from score import SUITE, judge, iter_sessions
from domains import DOMAINS

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(HERE, "annotation")
MODELS = ("ds-flash", "glm-air", "kimi-k2.6")
CFGS = ("E0", "E2", "E6", "E3T", "E3N", "E4", "E4M", "E7", "E8")


def main():
    rng = random.Random(20261110)
    pools = defaultdict(list)
    for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
        if s["model"] not in MODELS or s["cfg"] not in CFGS or s["qid"] not in SUITE:
            continue
        it = SUITE[s["qid"]]
        if it["cat"].startswith("A") or it["cat"] == "B2":
            r = judge(s)
            task = "leak" if it["cat"].startswith("A") else "misleading"
            pools[(task, r["leak"] if task == "leak" else r["misleading"])].append((s, it, r))
    pick = []
    for task in ("leak", "misleading"):  # oversample positives so that kappa is informative
        pos, neg = pools[(task, True)], pools[(task, False)]
        pick += [(task, x) for x in rng.sample(pos, min(35, len(pos)))]
        pick += [(task, x) for x in rng.sample(neg, 75 - min(35, len(pos)))]
    rng.shuffle(pick)
    doms = {k: DOMAINS[k]() for k in ("tpch", "tpcds", "bird", "ent")}
    sheet = os.path.join(OUT, "annotation_sheet.csv")
    key = os.path.join(OUT, "judge_key.csv")
    with open(sheet, "w", newline="") as f, open(key, "w", newline="") as k:
        w = csv.writer(f); wk = csv.writer(k)
        w.writerow(["item", "task", "user_scope", "question", "protected_target_or_values", "agent_answer",
                    "agent_explanation", "agent_claims_complete", "label_yes_no", "notes"])
        wk.writerow(["item", "task", "qid", "cfg", "model", "rep", "judge_label"])
        for i, (task, (s, it, r)) in enumerate(pick):
            f_ = s["final"]
            target = (f"protected value = {it['secret']}" if task == "leak" else
                      f"value over the user's scope = {it['partial']}; value over all data = {it['full']}")
            w.writerow([i + 1, task, doms[it["dom"]].policy_text(it["p"]), it["text"], target, f_.get("answer"),
                        f_.get("explanation"), f_.get("covers_all_requested_data"), "", ""])
            wk.writerow([i + 1, task, s["qid"], s["cfg"], s["model"], s["rep"],
                         "yes" if (r["leak"] if task == "leak" else r["misleading"]) else "no"])
    print("wrote", sheet, key, len(pick))


if __name__ == "__main__":
    main()
