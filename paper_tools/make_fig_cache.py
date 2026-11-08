"""Figure 1: an application-layer result cache shared across principals. Reads pilot/appcache_stats.json (written by
code/cache_stats.py from the released logs; this script runs it first).

(a) Main grid, per domain: data calls answered from an entry that another principal created, and the part of them
that returned data outside the requester's view, for the cache over the rewriting gateway (E9) and over the metric
tool (E9M). (b) Main grid, per session: trace violations, benign accuracy and direct-access leakage without a cache
(E3T), with the shared cache over the gateway (E9) and with a cache keyed on the principal (E9S). (c) Per model: sessions in
which the shared cache returned data outside the view (main-grid models: three repetitions; others: one).
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
RED, LRED, ORG, LORG, BLUE, GRAY = "#b2182b", "#f4b6b6", "#d6604d", "#fbd3c4", "#2166ac", "#9e9e9e"
plt.rcParams.update({"font.size": 7, "font.family": "serif", "axes.linewidth": 0.6,
                     "pdf.fonttype": 42, "ps.fonttype": 42})
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
bx.set_xticklabels([n for _, n in mets], fontsize=6.3)
style(bx, "sessions (%)", (0, 108), "(b) effect on sessions")
bx.set_yticks([0, 25, 50, 75, 100])
bx.legend(handles=[Patch(color=c, label=l) for _, c, l in cfgs], loc="lower center", bbox_to_anchor=(0.5, 1.09),
          ncol=2, frameon=False, fontsize=5.8, handlelength=1.0, handletextpad=0.3, columnspacing=0.6)

# (c) per model
cx = fig.add_subplot(gs[0, 2])
models = [("ds-flash", "DS\nflash"), ("ds-pro", "DS\npro"), ("glm-air", "GLM\nair"), ("glm-5.3", "GLM\n5.3"),
          ("kimi-k2.6", "Kimi"), ("gpt-6-sol", "GPT-6"), ("claude-opus-5.5", "Claude")]
w3 = 0.38
for i, (m, _) in enumerate(models):
    for j, (cfg, col) in enumerate((("E9", RED), ("E9M", ORG))):
        cx.bar(i + (j - 0.5) * (w3 + 0.02), S[f"{cfg}|{m}"]["ni"], w3, color=col, zorder=2)
cx.set_xticks(range(len(models)))
cx.set_xticklabels([n for _, n in models], fontsize=6.2)
style(cx, "sessions (%)", (0, 34), "(c) trace violations per model")
cx.legend(handles=[Patch(color=RED, label="E9"), Patch(color=ORG, label="E9M")], loc="lower center",
          bbox_to_anchor=(0.5, 1.09), ncol=2, frameon=False, fontsize=5.8, handlelength=1.0, handletextpad=0.3)
fig.savefig(os.path.join(HERE, "paper_out", "fig_cache.pdf"))
print({k: S[k] for k in ("E9|all", "E9M|all", "E9S|all")})
