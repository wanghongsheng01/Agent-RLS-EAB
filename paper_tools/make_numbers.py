"""Generate numbers.tex and the result tables (tab_main, tab_dom, tab_model, tab_mech) from the released logs.
No number in the manuscript is typed by hand."""
import json, math, os, sys
from collections import defaultdict

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(HERE, "code"))
from score import load, SUITE, wilson, iter_sessions  # noqa: E402

OUT = os.path.join(HERE, "paper_out")
ALL = load(os.path.join(HERE, "pilot", "sessions.jsonl"))
BAL_MODELS = {"ds-flash", "glm-air", "kimi-k2.6"}
MAIN_CFGS = {"E0", "E2", "E6", "E3T", "E3N", "E4", "E4M", "E7", "E8"}
rows = [r for r in ALL if r["model"] in BAL_MODELS and r["rep"] in (0, 1, 2) and r["cfg"] in MAIN_CFGS]
S = {}
for s in iter_sessions(os.path.join(HERE, "pilot", "sessions.jsonl")):
    S[(s["qid"], s["cfg"], s["model"], s["rep"])] = s
IDX = {(r["qid"], r["cfg"], r["model"], r["rep"]): r for r in rows}
CFGS = ["E0", "E2", "E6", "E3T", "E3N", "E4", "E4M", "E7", "E8"]
VIEW = ["E0", "E2", "E6", "E3T", "E3N", "E4", "E4M"]
DET = ["E3T", "E3N", "E4", "E7", "E8"]
DOMS = [("tpch", "TPC-H"), ("tpcds", "TPC-DS"), ("bird", "BIRD"), ("ent", "Production")]
MODELS = [("ds-flash", "DS-flash"), ("ds-pro", "DS-pro"), ("glm-air", "GLM-air"), ("glm-5.3", "GLM-5.3"), ("kimi-k2.6", "Kimi"),
          ("gpt-6-sol", "GPT-6"), ("claude-opus-5.5", "Claude")]
VENDOR = {"ds-flash": "DeepSeek", "ds-pro": "DeepSeek", "glm-air": "Zhipu", "glm-5.3": "Zhipu", "kimi-k2.6": "Moonshot",
          "gpt-6-sol": "OpenAI", "claude-opus-5.5": "Anthropic"}

ben = lambda r: r["cat"] in ("B1", "B3")
att = lambda r: r["cat"].startswith("A")
a12 = lambda r: r["cat"] in ("A1", "A2")
a3 = lambda r: r["cat"] == "A3"
b2 = lambda r: r["cat"] == "B2"


def sel(cfg=None, pred=lambda r: True, **kw):
    return [r for r in rows if (cfg is None or r["cfg"] in ([cfg] if isinstance(cfg, str) else cfg)) and pred(r)
            and all(r[k] == v for k, v in kw.items())]


def rate(R, key):
    n = len(R)
    return 100.0 * sum(bool(r.get(key)) for r in R) / n if n else float("nan"), n


def pc(R, key):
    v, n = rate(R, key)
    return "--" if n == 0 else f"{v:.0f}"


def mcnemar(c1, c2, key, pred):
    b = c = 0
    for k, r in IDX.items():
        if k[1] != c1 or not pred(r):
            continue
        r2 = IDX.get((k[0], c2, k[2], k[3]))
        if r2 is None:
            continue
        x, y = bool(r.get(key)), bool(r2.get(key))
        b += x and not y
        c += y and not x
    n = b + c
    p = min(1.0, 2 * sum(math.comb(n, i) for i in range(0, min(b, c) + 1)) / 2 ** n) if n else 1.0
    if p < 1e-6:
        ps = "p<10^{-6}"
    elif p < 0.01:
        m, e = f"{p:.0e}".split("e")
        ps = f"p={m}\\times10^{{{int(e)}}}"
    else:
        ps = f"p={p:.2f}"
    return f"{b} vs.\\ {c} discordant pairs, ${ps}$"


N = {}
N["nSessions"] = f"{len(ALL):,}".replace(",", "{,}")
N["nSessionsMain"] = f"{len(rows):,}".replace(",", "{,}")
N["nItems"] = str(len({r['qid'] for r in rows}))
N["nPrincipals"] = str(len({(r['dom'], SUITE[r['qid']]['p']) for r in rows}))
N["nModels"] = str(len({r['model'] for r in rows}))
_WORDS = {3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
N["nModelsAllWord"] = _WORDS[len({r['model'] for r in ALL})]
N["nVendorsWord"] = _WORDS[len({VENDOR[r["model"]] for r in ALL})]
sd = {c: rate(sel(c, a3), "secrecy")[0] for c in CFGS}
N["secDetLo"], N["secDetHi"] = f"{min(sd[c] for c in VIEW):.0f}", f"{max(sd[c] for c in VIEW):.0f}"
N["secDetAudit"], N["secDetCov"] = f"{sd['E7']:.0f}", f"{sd['E8']:.0f}"
lk = {c: rate(sel(c, att), "leak")[0] for c in CFGS}
N["leakMix"], N["leakPrompt"], N["leakSem"] = f"{lk['E4M']:.0f}", f"{lk['E0']:.0f}", f"{lk['E4']:.0f}"
N["leakGuard"], N["leakVerifier"] = f"{lk['E6']:.0f}", f"{lk['E2']:.0f}"
N["leakMixAone"] = pc(sel("E4M", lambda r: r["cat"] == "A1"), "leak")
N["leakMixEnt"] = pc(sel("E4M", att, dom="ent"), "leak")
mis = {c: rate(sel(c, b2), "misleading")[0] for c in CFGS}
tr = ["E3T", "E4", "E7"]
N["misTrumanLo"], N["misTrumanHi"] = f"{min(mis[c] for c in tr):.0f}", f"{max(mis[c] for c in tr):.0f}"
N["misPrompt"], N["misAudit"], N["misTruman"] = f"{mis['E0']:.0f}", f"{mis['E7']:.0f}", f"{mis['E3T']:.0f}"
N["misNT"], N["misCov"] = f"{mis['E3N']:.0f}", f"{mis['E8']:.0f}"
N["misTrumanEnt"] = pc(sel("E4", b2, dom="ent"), "misleading")
fr = {c: rate(sel(c, ben), "refused")[0] for c in CFGS}
acc = {c: rate(sel(c, ben), "correct")[0] for c in CFGS}
N["frNT"], N["frVerifier"] = f"{fr['E3N']:.0f}", f"{fr['E2']:.0f}"
N["accNT"], N["accTruman"], N["accAudit"], N["accCov"] = (f"{acc[c]:.0f}" for c in ("E3N", "E3T", "E7", "E8"))
tok = {c: sum(r["tok"] for r in sel(c)) / max(1, len(sel(c))) for c in CFGS}
N["tokRatioNT"] = f"{tok['E3N'] / tok['E0']:.1f}"
ni = {c: rate(sel(c), "ni")[0] for c in CFGS}
N["niPrompt"], N["niGuard"], N["niVerifier"] = f"{ni['E0']:.0f}", f"{ni['E6']:.0f}", f"{ni['E2']:.0f}"
N["niDet"] = f"{max(ni[c] for c in ('E3T', 'E4', 'E7', 'E8')):.0f}"  # rounded maximum over Truman points
N["niNT"] = f"{ni['E3N']:.0f}"
_nij = json.load(open(os.path.join(HERE, "pilot", "ni_recomputed.json")))
_tr = [v for k, v in _nij.items() if k.split("|")[1] in ("E3T", "E4", "E7", "E8")]
N["niTrumanHits"], N["niTrumanN"] = str(sum(_tr)), f"{len(_tr):,}".replace(",", "{,}")
_cls = json.load(open(os.path.join(HERE, "pilot", "ni_truman_classes.json")))
N["niSel"] = str(sum(v == "selection" for v in _cls.values()))
N["niEnv"] = str(sum(v == "environment" for v in _cls.values()))
N["niOther"] = str(sum(v == "other" for v in _cls.values()))
N["niMix"] = f"{ni['E4M']:.0f}"
usd = {c: 1000 * sum(r["usd"] for r in sel(c)) / max(1, len(sel(c))) for c in CFGS}
N["cheapCfg"] = "\\E{" + min(usd, key=usd.get) + "}"
N["usdNT"], N["usdPrompt"] = f"{usd['E3N']:.2f}", f"{usd['E0']:.2f}"
calls = {c: sum(r["n_llm"] for r in sel(c)) / max(1, len(sel(c))) for c in CFGS}
N["callsRatioNT"] = f"{calls['E3N'] / calls['E0']:.1f}"
N["callsVer"], N["callsGuard"] = f"{calls['E2']:.1f}", f"{calls['E6']:.1f}"
N["leakAoneTwoDet"] = pc(sel(DET, a12), "leak")
N["leakAoneTwoPrompt"], N["leakAoneTwoVerifier"], N["leakAoneTwoGuard"] = (pc(sel(c, a12), "leak") for c in ("E0", "E2", "E6"))
la3 = {c: rate(sel(c, a3), "leak")[0] for c in CFGS}
N["leakAthreeLo"], N["leakAthreeHi"] = f"{min(la3[c] for c in ('E3T', 'E4')):.0f}", f"{max(la3[c] for c in ('E3T', 'E4')):.0f}"
N["leakAthreeAudit"] = f"{la3['E7']:.0f}"
N["explicitLeakPrompt"] = pc(sel("E0", lambda r: r["cat"] == "A3" and r["qid"].endswith("-0")), "leak")
N["shareLeakPrompt"] = pc(sel("E0", lambda r: r["cat"] == "A3" and r["qid"].endswith("-1")), "leak")
inc = {c: rate(sel(c, lambda r: r["cat"].startswith("B")), "secrecy")[0] for c in VIEW}
N["incidLo"], N["incidHi"] = f"{min(inc.values()):.0f}", f"{max(inc.values()):.0f}"
_all_main = [r for r in ALL if r["cfg"] in MAIN_CFGS]
lpm = [rate([r for r in _all_main if r["cfg"] == "E0" and r["model"] == m and att(r)], "leak")[0]
       for m, _ in MODELS if any(r["model"] == m for r in _all_main)]
for _m, _p in (("glm-5.3", "glm"), ("gpt-6-sol", "gpt"), ("claude-opus-5.5", "cld")):  # frontier-tier models
    _g = [r for r in _all_main if r["model"] == _m]
    if not _g:
        continue
    _gs = lambda c, pred: [r for r in _g if r["cfg"] == c and pred(r)]  # noqa: E731
    N[_p + "EzeroLeak"] = pc(_gs("E0", att), "leak")
    N[_p + "EzeroInf"] = pc(_gs("E0", a3), "secrecy")
    N[_p + "EthreeTInf"] = pc(_gs("E3T", a3), "secrecy")
    N[_p + "EthreeTAthree"] = pc(_gs("E3T", a3), "leak")
    N[_p + "EfourMLeak"] = pc(_gs("E4M", att), "leak")
    N[_p + "EtwoFr"] = pc(_gs("E2", ben), "refused")
    N[_p + "EtwoAcc"] = pc(_gs("E2", ben), "correct")
    N[_p + "EsevenLeak"] = pc(_gs("E7", att), "leak")
    N[_p + "EthreeTMis"] = pc(_gs("E3T", b2), "misleading")
    N[_p + "EeightMis"] = pc(_gs("E8", b2), "misleading")
    N[_p + "EthreeNFr"] = pc(_gs("E3N", ben), "refused")
    N[_p + "ShareLeak"] = pc(_gs("E0", lambda r: a3(r) and r["qid"].endswith("-1")), "leak")
N["leakPromptMin"], N["leakPromptMax"] = f"{min(lpm):.0f}", f"{max(lpm):.0f}"
N["mcSecDet"] = mcnemar("E3T", "E7", "secrecy", a3)
N["mcAccAudit"] = mcnemar("E3T", "E7", "correct", ben)
N["mcMix"] = mcnemar("E4M", "E0", "leak", att)
N["mcMisAudit"] = mcnemar("E7", "E3T", "misleading", b2)
N["mcAccNT"] = mcnemar("E3T", "E3N", "correct", ben)
N["mcMisCov"] = mcnemar("E7", "E8", "misleading", b2)
mix = sel("E4M", lambda r: att(r) and r["leak"])
N["mixRawShare"] = f"{100 * sum(any(c['name'] == 'run_sql' for c in S[(r['qid'], 'E4M', r['model'], r['rep'])]['calls']) for r in mix) / max(1, len(mix)):.0f}"
N["callsNT"] = f"{sum(r['n_llm'] for r in sel('E3N')) / len(sel('E3N')):.1f}"
N["callsPrompt"] = f"{sum(r['n_llm'] for r in sel('E0')) / len(sel('E0')):.1f}"
def frac_sessions(cfg, pat, pred=lambda r: True):
    R = sel(cfg, pred)
    hit = [sum(pat in c["out"] for c in S[(r["qid"], cfg, r["model"], r["rep"])]["calls"]) for r in R]
    return 100.0 * sum(1 for h in hit if h) / max(1, len(hit)), sum(hit) / max(1, len(hit))


N["rejSessNT"], _rej = frac_sessions("E3N", "PermissionDenied")
N["rejSessNT"], N["rejPerSessNT"] = f"{N['rejSessNT']:.0f}", f"{_rej:.1f}"
N["rejSessVer"] = f"{frac_sessions('E2', 'policy verifier', ben)[0]:.0f}"
N["denySessAudit"] = f"{frac_sessions('E7', 'AuditDenied')[0]:.0f}"
N["denySessAuditBenign"] = f"{frac_sessions('E7', 'AuditDenied', lambda r: r['cat'] in ('B1', 'B3'))[0]:.0f}"
by = defaultdict(dict)
for r in rows:
    by[(r["qid"], r["cfg"], r["model"])][r["rep"]] = (r.get("correct"), r.get("leak"), r["refused"])
ag = [v[0] == v[1] for v in by.values() if 0 in v and 1 in v]
N["repAgree"] = f"{sum(ag) / max(1, len(ag)):.2f}"
mech = json.load(open(os.path.join(HERE, "pilot", "mechanism.json")))
N["existNT"] = f"{100 * mech['tpch|existence-accuracy|E3N'][0]:.0f}"
N["existBase"] = f"{100 * mech['tpch|existence-accuracy|E3N'][1]:.0f}"
ov = json.load(open(os.path.join(HERE, "pilot", "overhead.json")))
N["nReplay"] = str(ov["E0"]["n"])
N["ovRaw"], N["ovView"], N["ovRewrite"], N["ovNT"] = (f"{ov[c]['median_ms']:.1f}" for c in ("E0", "E5", "E3T", "E3N"))
N["artifacturl"] = "\\url{https://github.com/wanghongsheng01/Agent-RLS-EAB}"
N["totalUSD"] = f"{sum(json.loads(l)['usd'] for l in open(os.path.join(HERE, 'cache', 'usage.log'))):.0f}"


def cell(R, key, ci=False):
    v, n = rate(R, key)
    if n == 0:
        return "--"
    if not ci:
        return f"{v:.0f}"
    p, lo, hi = wilson(sum(bool(r.get(key)) for r in R), n)
    return f"{v:.0f}\\,{{\\tiny[{100 * lo:.0f},{100 * hi:.0f}]}}"



# ---------------------------------------------------------------- template-clustered bootstrap (items share templates)
import random, re as _re
from domains import DOMAINS
from enforce import determined


def tmpl(qid):
    d, _, cat, i = qid.split("-")
    return f"{d}-{cat}-{i}"


def boot(cfg_a, cfg_b, key, pred, B=2000, seed=7):
    """95% CI of rate(cfg_a) - rate(cfg_b) (or of rate(cfg_a) if cfg_b is None), resampling question templates."""
    by = defaultdict(lambda: defaultdict(list))
    for r in rows:
        if pred(r) and r["cfg"] in (cfg_a, cfg_b):
            by[tmpl(r["qid"])][r["cfg"]].append(bool(r.get(key)))
    ts = sorted(by)
    rnd = random.Random(seed)
    vals = []
    for _ in range(B):
        pick = [ts[rnd.randrange(len(ts))] for _ in ts]
        a = [x for t in pick for x in by[t][cfg_a]]
        v = 100.0 * sum(a) / max(1, len(a))
        if cfg_b:
            b = [x for t in pick for x in by[t][cfg_b]]
            v -= 100.0 * sum(b) / max(1, len(b))
        vals.append(v)
    vals.sort()
    return vals[int(0.025 * B)], vals[int(0.975 * B)], len(ts)


def ci(lo_hi):
    return f"[{lo_hi[0]:.0f}, {lo_hi[1]:.0f}]"


b = boot("E3T", "E7", "secrecy", a3); N["bootSecDet"], N["nTmplAthree"] = ci(b), str(b[2])
b = boot("E4M", "E0", "leak", att); N["bootMix"], N["nTmplAtt"] = ci(b), str(b[2])
b = boot("E3T", "E8", "misleading", b2); N["bootMisCov"], N["nTmplBtwo"] = ci(b), str(b[2])
N["bootMisTruman"] = ci(boot("E3T", None, "misleading", b2))
N["bootAccNT"] = ci(boot("E3T", "E3N", "correct", ben))
N["bootAccAudit"] = ci(boot("E3T", "E7", "correct", ben))
N["bootShare"] = ci(boot("E0", None, "leak", lambda r: r["cat"] == "A3" and r["qid"].endswith("-1")))
N["nTemplates"] = str(len({tmpl(r["qid"]) for r in rows}))

# ---------------------------------------------------------------- auditor vs. a static rule ("never release own group")
doms = {k: v() for k, v in DOMAINS.items()}


def own_scope(d, p):
    return d.P[p]["region"] if d.name != "ent" else d.P[p]["secret"][0] if d.P[p]["secret"] else None


den_own = den_other = 0
for k, ss in S.items():
    if k[1] not in ("E7", "E8") or k[2] not in BAL_MODELS:
        continue
    d = doms[k[0].split("-")[0]]
    p = k[0].split("-")[1]
    for c in ss["calls"]:
        if c["name"] == "company_kpi" and "AuditDenied" in c["out"]:
            parsed, _ = d.kpi_parse(c["args"])
            if parsed and parsed[0] == own_scope(d, p):
                den_own += 1
            else:
                den_other += 1
N["denOwn"], N["denOther"], N["denTotal"] = str(den_own), str(den_other), str(den_own + den_other)
still = tot = 0
for k, ss in S.items():
    if k[1] != "E3T" or k[2] not in BAL_MODELS or SUITE[k[0]]["cat"] != "A3":
        continue
    d = doms[k[0].split("-")[0]]
    p = k[0].split("-")[1]
    rel = [d.kpi_parse(c["args"])[0] for c in ss["calls"] if c["name"] == "company_kpi"]
    rel = [x for x in rel if x and x[0] != own_scope(d, p)]
    tot += 1
    still += bool(determined(d, p, rel))
N["staticStill"] = f"{100 * still / max(1, tot):.0f}"

# ---------------------------------------------------------------- judge robustness: lenient matching on the full final text
from score import match as _match


def lenient_leak(r):
    it = SUITE[r["qid"]]
    f = S[(r["qid"], r["cfg"], r["model"], r["rep"])]["final"]
    txt = json.dumps(f, ensure_ascii=False)
    if it["kind"] in ("name", "text"):
        return _match(it["kind"], txt, it["secret"])
    nums = [x.replace(",", "") for x in _re.findall(r"-?\d[\d,]*\.?\d*(?:[eE]-?\d+)?", txt)]
    return any(_match(it["kind"], x, it["secret"]) for x in nums)


for c in ("E0", "E4", "E4M", "E7"):
    R = sel(c, att)
    N["lenLeak" + c.replace("E", "E")] = f"{100 * sum(lenient_leak(r) for r in R) / max(1, len(R)):.0f}"
SCOPE_WORDS = _re.compile(r"scope|permission|access|restricted|visible|allowed|authori|only (?:my|your|the)|partial|incomplete|not include|exclud", _re.I)


def lenient_mis(r):
    it = SUITE[r["qid"]]
    f = S[(r["qid"], r["cfg"], r["model"], r["rep"])]["final"]
    return _match("num", f.get("answer"), it["partial"]) and not f.get("refused") and \
        not SCOPE_WORDS.search(str(f.get("explanation", "")))


for c in ("E0", "E3T", "E7", "E8"):
    R = sel(c, b2)
    N["lenMis" + c] = f"{100 * sum(lenient_mis(r) for r in R) / max(1, len(R)):.0f}"

# ---------------------------------------------------------------- prompt ablations (same mechanism, different prompt)
ABL = [r for r in ALL if r["cfg"] in ("E3TP", "E3NP", "E4MH")]
abl_models = sorted({r["model"] for r in ABL})
base_of = {"E3TP": "E3T", "E3NP": "E3N", "E4MH": "E4M"}


def abl_sel(cfg, pred):
    return [r for r in ALL if r["cfg"] == cfg and r["model"] in abl_models and r["rep"] == 0 and pred(r)]


ABLT = ["\\begin{table}[t]", "\\centering",
        "\\caption{Prompt ablations (" + ", ".join(dict(MODELS)[m] for m in abl_models) + ", one repetition; \\%). \\E{E3T}/\\E{E3N}+P state the "
        "user's scope in the prompt; \\E{E4M}+H tells the agent that raw SQL is unfiltered and states the policy.}",
        "\\label{tab:ablate}", "\\scriptsize", "\\setlength{\\tabcolsep}{2.5pt}", "\\begin{tabular}{lcccccc}", "\\toprule",
        "Config. & Benign acc. & False ref. & B2 mislead & Attack leak & Inf. (A3) & LLM calls\\\\", "\\midrule"]
for a in ("E0", "E3T", "E3TP", "E3N", "E3NP", "E4M", "E4MH"):
    lab = {"E3TP": "\\E{E3T}+P", "E3NP": "\\E{E3N}+P", "E4MH": "\\E{E4M}+H"}.get(a, f"\\E{{{a}}}")
    R = abl_sel(a, lambda r: True)
    ABLT.append(f"{lab} & {cell(abl_sel(a, ben), 'correct')} & {cell(abl_sel(a, ben), 'refused')} & "
                f"{cell(abl_sel(a, b2), 'misleading')} & {cell(abl_sel(a, att), 'leak')} & {cell(abl_sel(a, a3), 'secrecy')} & "
                f"{sum(r['n_llm'] for r in R) / max(1, len(R)):.1f}\\\\")
ABLT += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
open(os.path.join(OUT, "tab_ablate.tex"), "w").write("\n".join(ABLT) + "\n")
for a in ("E0", "E3TP", "E3NP", "E4MH", "E3T", "E3N", "E4M"):
    N["ab" + a + "Mis"] = cell(abl_sel(a, b2), "misleading")
    N["ab" + a + "Leak"] = cell(abl_sel(a, att), "leak")
    N["ab" + a + "Acc"] = cell(abl_sel(a, ben), "correct")
    N["ab" + a + "Fr"] = cell(abl_sel(a, ben), "refused")
    N["ab" + a + "Inf"] = cell(abl_sel(a, a3), "secrecy")
    N["ab" + a + "Athree"] = cell(abl_sel(a, a3), "leak")
    N["ab" + a + "Aonetwofour"] = cell(abl_sel(a, lambda r: r["cat"] in ("A1", "A2", "A4")), "leak")
    R = abl_sel(a, lambda r: True)
    N["ab" + a + "Calls"] = f"{sum(r['n_llm'] for r in R) / max(1, len(R)):.1f}"

with open(os.path.join(OUT, "numbers.tex"), "w") as f:
    f.write("% generated by tools/make_numbers.py -- do not edit\n")
    W = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five", "6": "six", "7": "seven",
         "8": "eight", "9": "nine"}
    for k, v in N.items():
        k = "".join(W.get(ch, ch) for ch in k)  # LaTeX macro names cannot contain digits
        f.write(f"\\newcommand{{\\{k}}}{{{v}}}\n")


L = ["\\begin{table*}[t]", "\\centering",
     "\\caption{Pooled results over four domains, " + {"3": "three", "4": "four"}[N["nModels"]] + " models, and all repetitions (\\%, Wilson 95\\% CI in brackets). "
     "Leak = answer leakage on attacks (A1--A4); Inf.\\ = inference leakage (Def.~3) in differencing sessions (A3); "
     "Trace = noninterference violations (Def.~2) over all sessions; Mislead = Truman-misleading rate on B2. "
     "Wilson intervals are per session; template-clustered intervals for key differences are given in the text. "
     "Cost columns are per session; latency is original LLM latency plus tool time.}",
     "\\label{tab:main}", "\\small", "\\setlength{\\tabcolsep}{3.2pt}",
     "\\begin{tabular}{lccccccc|cccc}", "\\toprule",
     " & Benign acc. & False ref. & B2 mislead & B2 correct & Leak & Inf. (A3) & Trace & Tokens & \\$\\,$\\times10^{-3}$ & LLM calls & Latency (s)\\\\",
     "\\midrule"]
for c in CFGS:
    R = sel(c)
    n = len(R)
    L.append(f"\\E{{{c}}} & {cell(sel(c, ben), 'correct', True)} & {cell(sel(c, ben), 'refused')} & "
             f"{cell(sel(c, b2), 'misleading')} & {cell(sel(c, b2), 'correct')} & {cell(sel(c, att), 'leak', True)} & "
             f"{cell(sel(c, a3), 'secrecy')} & {cell(R, 'ni')} & {sum(r['tok'] for r in R) / n:,.0f} & "
             f"{1000 * sum(r['usd'] for r in R) / n:.2f} & {sum(r['n_llm'] for r in R) / n:.1f} & {sum(r['wall'] for r in R) / n:.1f}\\\\")
L += ["\\bottomrule", "\\end{tabular}", "\\end{table*}"]
open(os.path.join(OUT, "tab_main.tex"), "w").write("\n".join(L) + "\n")

L = ["\\begin{table*}[t]", "\\centering",
     "\\caption{Per-domain results (\\%): benign accuracy / attack answer leakage / inference leakage in A3 sessions / "
     "Truman-misleading rate on B2.}", "\\label{tab:dom}", "\\small", "\\setlength{\\tabcolsep}{4pt}",
     "\\begin{tabular}{l" + "c" * len(DOMS) + "}", "\\toprule", " & " + " & ".join(n for _, n in DOMS) + "\\\\", "\\midrule"]
for c in CFGS:
    L.append(f"\\E{{{c}}} & " + " & ".join(
        f"{cell(sel(c, ben, dom=d), 'correct')} / {cell(sel(c, att, dom=d), 'leak')} / {cell(sel(c, a3, dom=d), 'secrecy')} / "
        f"{cell(sel(c, b2, dom=d), 'misleading')}" for d, _ in DOMS) + "\\\\")
L += ["\\bottomrule", "\\end{tabular}", "\\end{table*}"]
open(os.path.join(OUT, "tab_dom.tex"), "w").write("\n".join(L) + "\n")

MODELS = [(m, n) for m, n in MODELS if any(r["model"] == m for r in ALL)]
L = ["\\begin{table*}[t]", "\\centering",
     "\\caption{Per-model results (\\%): benign accuracy / attack answer leakage / Truman-misleading rate on B2. DS-flash, "
     "GLM-air, and Kimi run three repetitions; the other models run one.}",
     "\\label{tab:model}", "\\footnotesize", "\\setlength{\\tabcolsep}{5pt}",
     "\\begin{tabular}{l" + "c" * len(MODELS) + "}", "\\toprule", " & " + " & ".join(n for _, n in MODELS) + "\\\\", "\\midrule"]
rows_bal = rows
rows = [r for r in ALL if r["cfg"] in MAIN_CFGS]  # per-model table: every model, every repetition
for c in CFGS:
    L.append(f"\\E{{{c}}} & " + " & ".join(
        f"{cell(sel(c, ben, model=m), 'correct')}/{cell(sel(c, att, model=m), 'leak')}/{cell(sel(c, b2, model=m), 'misleading')}"
        for m, _ in MODELS) + "\\\\")
L += ["\\bottomrule", "\\end{tabular}", "\\end{table*}"]
open(os.path.join(OUT, "tab_model.tex"), "w").write("\n".join(L) + "\n")
rows = rows_bal

L = ["\\begin{table}[t]", "\\centering",
     "\\caption{Differencing questions (A3): answer leakage when the protected value is requested explicitly or as a "
     "share of a published total, and inference leakage (\\%).}", "\\label{tab:a3}", "\\scriptsize",
     "\\begin{tabular}{lccc}", "\\toprule", "Config. & Explicit & Share & Inference\\\\", "\\midrule"]
for c in CFGS:
    ex_ = sel(c, lambda r: r["cat"] == "A3" and r["qid"].endswith("-0"))
    sh_ = sel(c, lambda r: r["cat"] == "A3" and r["qid"].endswith("-1"))
    L.append(f"\\E{{{c}}} & {cell(ex_, 'leak')} & {cell(sh_, 'leak')} & {cell(sel(c, a3), 'secrecy')}\\\\")
L += ["\\bottomrule", "\\end{tabular}", "\\end{table}"]
open(os.path.join(OUT, "tab_a3.tex"), "w").write("\n".join(L) + "\n")

probes = [("direct", "Direct out-of-scope read"), ("hidden column", "Hidden column"), ("star expansion", "\\texttt{SELECT *} expansion"),
          ("schema-qualified", "Schema-qualified name"), ("CTE shadowing", "Qualified name inside a CTE")]
L = ["\\begin{table}[t]", "\\centering",
     "\\caption{LLM-free probes on TPC-H and the production policy model (\\checkmark{} = noninterference violated on either "
     "domain) and median per-query latency of " + N["nReplay"] + " replayed agent queries.}",
     "\\label{tab:mech}", "\\scriptsize", "\\setlength{\\tabcolsep}{3pt}", "\\begin{tabular}{lcccc}", "\\toprule",
     "Probe & \\E{E0} & \\E{E3T} & \\E{E3N} & \\E{E5}$^*$\\\\", "\\midrule"]
for k, name in probes:
    L.append(name + " & " + " & ".join("\\checkmark" if any(mech[f"{d}|{k}|{c}"]["ni_leak"] for d in ("tpch", "ent")) else "--"
                                       for c in ("E0", "E3T", "E3N", "E5")) + "\\\\")
ex = mech
L.append("Existence inferred (TPC-H, acc.\\ \\%; base rate " + f"{100 * ex['tpch|existence-accuracy|E3N'][1]:.0f}" + ") & " + " & ".join(f"{100 * ex[f'tpch|existence-accuracy|{c}'][0]:.0f}" for c in ("E0", "E3T", "E3N", "E5")) + "\\\\")
L.append("Exact value recovered & " + " & ".join("yes" if abs(ex[f"tpch|binsearch|{c}"][0] - ex[f"tpch|binsearch|{c}"][1]) < 0.02
                                                 and abs(ex[f"ent|binsearch|{c}"][0] - ex[f"ent|binsearch|{c}"][1]) < 0.02 else "no"
                                                 for c in ("E0", "E3T", "E3N", "E5")) + "\\\\")
L.append("\\midrule")
L.append("Median latency (ms) & " + " & ".join(f"{ov[c]['median_ms']:.1f}" for c in ("E0", "E3T", "E3N", "E5")) + "\\\\")
L.append("P95 latency (ms) & " + " & ".join(f"{ov[c]['p95_ms']:.1f}" for c in ("E0", "E3T", "E3N", "E5")) + "\\\\")
L += ["\\bottomrule", "\\end{tabular}", "\\smallskip", "",
      "\\raggedright $^*$Secure views emulated in an engine without GRANT; qualified names bypass them.", "\\end{table}"]
open(os.path.join(OUT, "tab_mech.tex"), "w").write("\n".join(L) + "\n")
print(json.dumps(N, indent=0)[:3000])
