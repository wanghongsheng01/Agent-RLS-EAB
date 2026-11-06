"""Figure 1: per-configuration trade-offs, pooled over domains, models and repetitions (from the released logs).

Two-column figure with broken x-axes: the configurations cluster near 93% accuracy and near 0% refusals, so a
continuous axis stacks their markers on top of each other. Every point carries a direct label instead of a legend.
"""
import os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(HERE, "code"))
from score import load  # noqa: E402

rows = [r for r in load(os.path.join(HERE, "pilot", "sessions.jsonl"))
        if r["model"] in ("ds-flash", "glm-air", "kimi-k2.6")]  # balanced main grid, as in Table IV
CFGS = ["E0", "E2", "E6", "E3T", "E3N", "E4", "E4M", "E7", "E8"]
RED, BLUE, GREEN = "#b2182b", "#2166ac", "#1b7837"
COL = {c: RED for c in ("E0", "E2", "E6")} | {c: BLUE for c in ("E3T", "E3N", "E4", "E4M")} | \
      {c: GREEN for c in ("E7", "E8")}
MARK = {"E0": "o", "E2": "s", "E6": "D", "E3T": "^", "E3N": "v", "E4": "<", "E4M": ">", "E7": "P", "E8": "X"}
# label offsets in points (dx, dy); chosen so that no label covers a marker or another label
OFF_A = {"E0": (5, 0), "E2": (-5, 4), "E6": (5, 0), "E3T": (5, 2), "E3N": (5, 0), "E4": (-5, -4), "E4M": (5, 0),
         "E7": (5, 0), "E8": (-4, -5)}
OFF_B = {"E0": (-4, 5), "E2": (5, 0), "E6": (4, 5), "E3T": (5, 0), "E3N": (0, 6), "E4": (-5, -4), "E4M": (-5, 3),
         "E7": (5, 0), "E8": (-5, 0)}


def rate(cfg, key, pred):
    R = [r for r in rows if r["cfg"] == cfg and pred(r) and key in r]
    return 100.0 * sum(bool(r[key]) for r in R) / max(1, len(R))


pts = {}
for c in CFGS:
    benign = lambda r: r["cat"] in ("B1", "B3")  # noqa: E731
    pts[c] = {"acc": rate(c, "correct", benign), "fr": rate(c, "refused", benign),
              "leak": rate(c, "leak", lambda r: r["cat"].startswith("A")),
              "mis": rate(c, "misleading", lambda r: r["cat"] == "B2")}

plt.rcParams.update({"font.size": 7, "font.family": "serif", "axes.linewidth": 0.6,
                     "pdf.fonttype": 42, "ps.fonttype": 42})  # embed TrueType, not Type 3
fig = plt.figure(figsize=(7.0, 2.05))
gs = fig.add_gridspec(1, 5, width_ratios=[1.0, 3.0, 0.42, 3.0, 1.0], wspace=0.05,
                      left=0.06, right=0.99, bottom=0.17, top=0.83)


def broken(ax_l, ax_r, xl, xr, ylim):
    """Two axes that share y and show one broken x-axis."""
    for a, xlim in ((ax_l, xl), (ax_r, xr)):
        a.set_xlim(*xlim)
        a.set_ylim(*ylim)
        a.grid(alpha=0.3, linewidth=0.4)
        a.tick_params(length=2, pad=1.5)
    ax_l.spines["right"].set_visible(False)
    ax_r.spines["left"].set_visible(False)
    ax_r.tick_params(left=False, labelleft=False)
    d = dict(marker=[(-0.5, -1), (0.5, 1)], markersize=5, linestyle="none", color="k", mec="k", mew=0.6,
             clip_on=False)
    ax_l.plot([1, 1], [0, 1], transform=ax_l.transAxes, **d)
    ax_r.plot([0, 0], [0, 1], transform=ax_r.transAxes, **d)


def panel(ax_l, ax_r, xk, yk, off, split):
    for c in CFGS:
        x, y = pts[c][xk], pts[c][yk]
        a = ax_l if x < split else ax_r
        a.scatter(x, y, s=22, marker=MARK[c], color=COL[c], edgecolor="white", linewidth=0.3, zorder=3)
        dx, dy = off[c]
        a.annotate(c, (x, y), xytext=(dx, dy), textcoords="offset points", fontsize=6.5, color=COL[c],
                   ha="left" if dx > 0 else ("right" if dx < 0 else "center"), va="center", zorder=4)


a1, a2 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])
broken(a1, a2, (61, 66), (90.6, 96.6), (-10, 90))
panel(a1, a2, "acc", "leak", OFF_A, 80)
a1.set_xticks([62, 65])
a1.set_ylabel("attack answer leakage (%)")
a2.set_xlabel("benign accuracy (%)", labelpad=1, x=0.37)
a2.set_title("(a) leakage vs. utility (better: lower right)", fontsize=7, x=0.37)

b1, b2 = fig.add_subplot(gs[0, 3]), fig.add_subplot(gs[0, 4])
broken(b1, b2, (-0.7, 3.3), (26.0, 29.0), (-6, 74))
panel(b1, b2, "fr", "mis", OFF_B, 15)
b2.set_xticks([27, 28])
b1.set_ylabel("misleading on B2 (%)", labelpad=1)
b1.set_xlabel("benign false refusals (%)", labelpad=1, x=0.63)
b1.set_title("(b) misleading vs. refusals (better: lower left)", fontsize=7, x=0.63)

fam = [Line2D([], [], marker="o", linestyle="none", markersize=4, color=c, label=l)
       for c, l in ((RED, "model-side (E0, E2, E6)"), (BLUE, "per-call deterministic (E3T, E3N, E4, E4M)"),
                    (GREEN, "session auditing (E7, E8)"))]
fig.legend(handles=fam, loc="upper center", ncol=3, frameon=False, fontsize=6.5, handletextpad=0.2,
           columnspacing=1.6, bbox_to_anchor=(0.5, 1.0))
fig.savefig(os.path.join(HERE, "paper", "fig_tradeoff.pdf"))
print({c: {k: round(v, 1) for k, v in p.items()} for c, p in pts.items()})
