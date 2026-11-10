"""Figure 1: an application-layer result cache shared across principals. Reads pilot/appcache_stats.json (written by
code/cache_stats.py from the released logs; this script runs it first).

(a) Main grid, per domain: data calls answered from an entry that another principal created, and the part of them
that returned data outside the requester's view, for the cache over the rewriting gateway (E9) and over the metric
tool (E9M). (b) Main grid, per session: trace violations, benign accuracy and direct-access leakage without a cache
(E3T), with the shared cache over the gateway (E9) and with a cache keyed on the principal (E9S). (c) Data calls served
from the cache on the uncached gateway's trajectories, by cache key, with 1, 3, or 9 users per role
(code/cache_designs.py); the dark part of the shared cache's bar returned another scope's result.
"""
import json, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(os.path.join(HERE, "paper_out"), exist_ok=True)
sys.path.insert(0, os.path.join(HERE, "code"))
import cache_stats  # noqa: E402

cache_stats.main()
S = json.load(open(os.path.join(HERE, "pilot", "appcache_stats.json")))
# Okabe-Ito (color-blind safe): vermillion and reddish purple with light tints, blue, sky blue, gray
RED, LRED, ORG, LORG, BLUE, GRAY = "#D55E00", "#F3C3A0", "#CC79A7", "#EED3E3", "#0072B2", "#999999"
plt.rcParams.update({"font.size": 7, "font.family": "serif", "font.serif": ["Times New Roman", "STIXGeneral"], "mathtext.fontset": "stix",
                     "axes.linewidth": 0.6, "pdf.fonttype": 42, "ps.fonttype": 42})  # Times-like, as the body text; embed TrueType
fig = plt.figure(figsize=(7.0, 2.15))
gs = fig.add_gridspec(1, 3, width_ratios=[1.25, 0.95, 1.5], wspace=0.28, left=0.055, right=0.995, bottom=0.2,
                      top=0.74)


def style(ax, ylabel, ylim, title):
    ax.set_ylim(*ylim)
    ax.set_ylabel(ylabel, labelpad=1)
    ax.grid(axis="y", alpha=0.3, linewidth=0.4, zorder=0)
    ax.tick_params(length=2, pad=1.5)
    ax.set_title(title, fontsize=7, pad=3)


# (a) per domain
ax = fig.add_subplot(gs[0, 0])
doms = [("tpch", "TPC-H"), ("tpcds", "TPC-DS"), ("bird", "BIRD"), ("ent", "Prod."), ("all", "All")]
w = 0.38
for i, (d, _) in enumerate(doms):
    for j, (cfg, light, dark) in enumerate((("E9", LRED, RED), ("E9M", LORG, ORG))):
        o = S[f"{cfg}|{d}"]
        x = i + (j - 0.5) * (w + 0.02)
        ax.bar(x, o["cross_hit"], w, color=light, zorder=2)
        ax.bar(x, o["overpriv"], w * 0.6, color=dark, zorder=3)
ax.set_xticks(range(len(doms)))
ax.set_xticklabels([n for _, n in doms], fontsize=6.3)
style(ax, "data calls (%)", (0, 34), "(a) data calls answered by the shared cache")
ax.legend(handles=[Patch(color=LRED, label="E9: other principal's entry"),
                   Patch(color=RED, label="E9: outside the view"),
                   Patch(color=LORG, label="E9M: other principal's entry"),
                   Patch(color=ORG, label="E9M: outside the view")],
          loc="lower center", bbox_to_anchor=(0.5, 1.09), ncol=2, frameon=False, fontsize=5.8, handlelength=1.0,
          handletextpad=0.3, columnspacing=0.6)

# (b) per session, main grid
bx = fig.add_subplot(gs[0, 1])
mets = [("ni", "trace\nviolations"), ("acc", "benign\naccuracy"), ("leak_direct", "direct\nleakage")]
cfgs = [("E3T", GRAY, "no cache (E3T)"), ("E9", RED, "shared (E9)"), ("E9S", BLUE, "per principal (E9S)")]
w2 = 0.27
for i, (k, _) in enumerate(mets):
    for j, (cfg, col, _) in enumerate(cfgs):
        v = S[f"{cfg}|all"][k]
        x = i + (j - 1) * w2
        bx.bar(x, v, w2 * 0.9, color=col, zorder=2)
        bx.text(x, v + 1.5, f"{v:.0f}", ha="center", va="bottom", fontsize=5.0)
bx.set_xticks(range(len(mets)))
bx.set_xticklabels([n for _, n in mets], fontsize=6.3, linespacing=1.3)
style(bx, "sessions (%)", (0, 108), "(b) effect on sessions")
bx.set_yticks([0, 25, 50, 75, 100])
bx.legend(handles=[Patch(color=c, label=l) for _, c, l in cfgs], loc="lower center", bbox_to_anchor=(0.5, 1.09),
          ncol=2, frameon=False, fontsize=5.8, handlelength=1.0, handletextpad=0.3, columnspacing=0.6)

# (c) reuse by cache key (LLM-free replay of the E3T trajectories, code/cache_designs.py), k users per role
CD = json.load(open(os.path.join(HERE, "pilot", "cache_designs.json")))
cx = fig.add_subplot(gs[0, 2])
keys = [("shared", LRED, "request"), ("user", GRAY, "request+user"), ("scope", BLUE, "request+scope"),
        ("below", "#56B4E9", "below gateway")]
w3 = 0.2
for i, k in enumerate(("1", "3", "9")):
    for j, (x, col, _) in enumerate(keys):
        o = CD[k][x]
        xx = i + (j - 1.5) * w3
        if x == "shared":  # stacked: another scope's result at the bottom, correct reuse above it
            wrong = o["hit"] * o["diff_of_hits"] / 100
            cx.bar(xx, wrong, w3 * 0.92, color=RED, zorder=2)
            cx.bar(xx, o["hit"] - wrong, w3 * 0.92, bottom=wrong, color=col, zorder=2)
        else:
            cx.bar(xx, o["hit"], w3 * 0.92, color=col, zorder=2)
        cx.text(xx, o["hit"] + 0.8, f"{o['hit']:.0f}", ha="center", va="bottom", fontsize=4.6)
cx.set_xticks(range(3))
cx.set_xticklabels(["1", "3", "9"], fontsize=6.3)
cx.set_xlabel("users per role", labelpad=1)
style(cx, "data calls served (%)", (0, 66), "(c) reuse by cache key, per role")
cx.legend(handles=[Patch(color=c, label=l) for _, c, l in keys] + [Patch(color=RED, label="other scope")],
          loc="lower center", bbox_to_anchor=(0.5, 1.09), ncol=3, frameon=False, fontsize=5.8, handlelength=1.0,
          handletextpad=0.3, columnspacing=0.6)
fig.savefig(os.path.join(HERE, "paper_out", "fig_cache.pdf"))
print({k: S[k] for k in ("E9|all", "E9M|all", "E9S|all")})
