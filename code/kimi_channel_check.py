"""Consistency of Kimi-K2.6 across access channels: sessions re-run through the organization's gateway
(pilot/kimi_channel_check.jsonl; E0 and E3T, repetition 0, TPC-H and BIRD) against the vendor API's sessions of the
same questions (repetition 0), with the vendor's repetition 1 as the baseline of run-to-run variation (temperature 0.6).
Writes pilot/kimi_channel_check.json."""
import json, os, statistics

from score import judge, iter_sessions

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def outcome(s):
    r = judge(s)
    c = r["cat"]
    v = r.get("correct") if c in ("B1", "B3") else (r.get("misleading") if c == "B2" else r.get("leak"))
    return c, bool(v)


def main():
    gw = {}
    for l in open(os.path.join(HERE, "pilot", "kimi_channel_check.jsonl")):
        s = json.loads(l)
        gw[(s["qid"], s["cfg"])] = s
    off = {}
    for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
        if s["model"] == "kimi-k2.6" and s["cfg"] in ("E0", "E3T") and s["rep"] in (0, 1) and (s["qid"], s["cfg"]) in gw:
            off[(s["qid"], s["cfg"], s["rep"])] = s
    keys = [k for k in gw if (k[0], k[1], 0) in off and (k[0], k[1], 1) in off]
    agree_gw = sum(outcome(gw[k])[1] == outcome(off[(k[0], k[1], 0)])[1] for k in keys)
    agree_rep = sum(outcome(off[(k[0], k[1], 1)])[1] == outcome(off[(k[0], k[1], 0)])[1] for k in keys)
    def rate(ss, pred):
        xs = [outcome(s)[1] for s in ss if pred(outcome(s)[0])]
        return round(100 * sum(xs) / len(xs), 1) if xs else None
    G = [gw[k] for k in keys]; O = [off[(k[0], k[1], 0)] for k in keys]
    out = {"sessions": len(keys),
           "outcome_agreement_gateway_vs_vendor": round(100 * agree_gw / len(keys), 1),
           "outcome_agreement_vendor_rep1_vs_rep0": round(100 * agree_rep / len(keys), 1),
           "median_output_tokens": {"gateway": statistics.median(s["usage"]["ct"] for s in G),
                                    "vendor": statistics.median(s["usage"]["ct"] for s in O)},
           "mean_llm_calls": {"gateway": round(statistics.mean(s["usage"]["n_llm"] for s in G), 2),
                              "vendor": round(statistics.mean(s["usage"]["n_llm"] for s in O), 2)},
           "benign_accuracy": {"gateway": rate(G, lambda c: c in ("B1", "B3")), "vendor": rate(O, lambda c: c in ("B1", "B3"))},
           "attack_leakage": {"gateway": rate(G, lambda c: c.startswith("A")), "vendor": rate(O, lambda c: c.startswith("A"))},
           "misleading": {"gateway": rate(G, lambda c: c == "B2"), "vendor": rate(O, lambda c: c == "B2")}}
    json.dump(out, open(os.path.join(HERE, "pilot", "kimi_channel_check.json"), "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
