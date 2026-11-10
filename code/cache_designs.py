"""Safe cache designs and their reuse (LLM-free replay; RQ2). A cache keyed on the scope returns exactly the result
that a fresh execution under the requester's policy returns, so agent trajectories are those of the uncached gateway:
the replay reuses the logged E3T sessions of the main grid (three models x three repetitions) and changes only the
cache. A deployment runs one agent model and has k users per role (k = 1, 3, 9); each user asks a random half of the
role's questions, and each of its sessions is one of the model's three logged repetitions of that question, drawn at
random; the sessions of all users of a domain run in one shuffled order (five shuffles per domain and model). Cache keys:
  user   request + user identity (per-user cache)
  scope  request + the role's policy (cache keyed on the scope)
  below  the SQL text after rewriting, i.e. a cache placed below the enforcement point
  shared request only (E9's key; reported as reuse potential on the same trajectories, with the share of hits whose
         result differs from the requester's own result)
Errors and rejections are never cached. Writes pilot/cache_designs.json.
"""
import json, os, random, re
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = ("ds-flash", "glm-air", "kimi-k2.6")
DOMS = ("tpch", "tpcds", "bird", "ent")


def norm(s):
    return re.sub(r"\s+", " ", (s or "").strip().rstrip(";")).lower()


def is_err(out):
    return out.lstrip().startswith('{"error"')


def load():
    by = defaultdict(list)  # (dom, p, model, rep) -> sessions
    for l in open(os.path.join(HERE, "pilot", "sessions.jsonl")):
        s = json.loads(l)
        if s["cfg"] == "E3T" and s["model"] in MODELS and "-C" not in s["qid"]:
            dom, p = s["qid"].split("-")[:2]
            by[(dom, p, s["model"], s["rep"])].append(s)
    return by


def simulate(by, dom, model, k, seed):
    """One deployment: one agent model; k users per role (the domain's principals); each user asks a random half of the
    role's questions, and each of its sessions is one of the model's logged repetitions of that question, drawn at
    random (a deterministic agent answers a repeated question as in another repetition)."""
    rng = random.Random(f"{dom}-{model}-{k}-{seed}")
    seq = []
    for (d, p, m, r), ss in by.items():
        if d != dom or m != model or r != 0:
            continue
        reps = {q: [by[(d, p, m, rr)] for rr in (0, 1, 2) if (d, p, m, rr) in by] for q in [x["qid"] for x in ss]}
        qids = sorted(reps)
        for u in range(k):
            for q in rng.sample(qids, len(qids) // 2):
                cand = [x for rs in reps[q] for x in rs if x["qid"] == q]
                seq.append((p, u, rng.choice(cand)))
    rng.shuffle(seq)
    caches = {x: {} for x in ("user", "scope", "below", "shared")}
    st = {x: defaultdict(int) for x in caches}
    for p, u, s in seq:
        for c in s["calls"]:
            if c["name"] != "run_sql":
                continue
            req, out = norm(c["args"].get("sql", "")), c["out"]
            keys = {"user": (p, u, req), "scope": (p, req), "below": norm(c.get("sql")) if c.get("sql") else None,
                    "shared": req}
            for x, key in keys.items():
                st[x]["lookups"] += 1
                if key is None or is_err(out):
                    continue
                if key in caches[x]:
                    st[x]["hits"] += 1
                    o_owner, ou = caches[x][key]
                    st[x]["cross_user"] += ou != (p, u)
                    st[x]["diff"] += o_owner != out
                else:
                    caches[x][key] = (out, (p, u))
    return st


def main():
    by = load()
    res = {}
    for k in (1, 3, 9):
        tot = {x: defaultdict(int) for x in ("user", "scope", "below", "shared")}
        for dom in DOMS:
            for model in MODELS:
                for seed in range(5):
                    st = simulate(by, dom, model, k, seed)
                    for x in st:
                        for f, v in st[x].items():
                            tot[x][f] += v
        res[k] = {x: {"hit": round(100 * t["hits"] / t["lookups"], 1),
                      "diff_of_hits": round(100 * t["diff"] / t["hits"], 1) if t["hits"] else 0.0,
                      "cross_user_of_hits": round(100 * t["cross_user"] / t["hits"], 1) if t["hits"] else 0.0,
                      "lookups": t["lookups"]} for x, t in tot.items()}
    json.dump(res, open(os.path.join(HERE, "pilot", "cache_designs.json"), "w"), indent=1)
    for k, v in res.items():
        print(k, v)


if __name__ == "__main__":
    main()
