"""Comparative analysis: all four techniques on (a) a synthetic benchmark with known ground truth and
(b) all four real recordings (clean segments). Ranks them and writes the winner to comparison/winner.json."""
import json, os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from emg_lib import *
OUT = os.path.join(HERE, "comparison"); os.makedirs(OUT, exist_ok=True)
TECHS = list(CHAINS); WHO = {v: k for k, v in MEMBER_TECHNIQUE.items()}

# ---- synthetic benchmark ----
rows = []
for sc, kw in SCEN.items():
    for seed in SYN_SEEDS:
        data = synth(SYN_SEED_BASE + seed, **kw)
        for tech in TECHS: m = synth_metrics(tech, *data); m.update(scenario=sc, seed=seed, technique=tech); rows.append(m)
S = pd.DataFrame(rows); S.round(3).to_csv(f"{OUT}/synthetic_all.csv", index=False)
Ssum = S.groupby(["technique", "scenario"])[["F1", "corr", "lag_ms", "FP_per_min", "delay_ms"]].mean().round(3); Ssum.to_csv(f"{OUT}/synthetic_by_scenario.csv")

# ---- real recordings ----
rr, store = [], {}
for name in FILES:
    t, x = load(name); runs = runs_from(score_windows(x))
    for tech in TECHS:
        env, clean = run_chain(tech, x); m = real_metrics(env, clean, runs); m.update(recording=name, technique=tech); rr.append(m)
        if name == "Prashant": store[tech] = env
R = pd.DataFrame(rr); R.round(3).to_csv(f"{OUT}/real_all.csv", index=False)

# ---- ranking ----
# Three categories matching the project aims. Ties (differences below the stated tolerance) share the better rank.
sy = S.groupby("technique")[["F1", "corr", "FP_per_min", "lag_ms", "realtime_factor"]].mean(); rl = R.groupby("technique")[["stride_CV", "rhythm_score", "mains_residual_pct", "strides_per_min"]].mean()
T = pd.concat([sy, rl], axis=1).loc[TECHS]
def rk(col, asc, tol):
    v = T[col].values; order = np.argsort(v if asc else -v); r = np.zeros(len(v)); cur = 1
    for i, j in enumerate(order):
        if i > 0 and abs(v[j] - v[order[i-1]]) > tol: cur = i + 1
        r[j] = cur
    return pd.Series(r, index=T.index)
rank = pd.DataFrame({"F1": rk("F1", False, .02), "FP_per_min": rk("FP_per_min", True, 1.0), "lag_ms": rk("lag_ms", True, 5), "corr": rk("corr", False, .02), "rhythm_score": rk("rhythm_score", False, .02)})
T["cat_detection"] = rank[["F1", "FP_per_min"]].mean(axis=1); T["cat_responsiveness"] = rank["lag_ms"]; T["cat_fidelity"] = rank[["corr", "rhythm_score"]].mean(axis=1)
WEIGHTS = dict(cat_detection=.5, cat_responsiveness=.25, cat_fidelity=.25)          # detection matters most for step control
T["score_weighted"] = sum(T[c]*w for c, w in WEIGHTS.items()); T["score_equal"] = T[list(WEIGHTS)].mean(axis=1)
T["worst_scenario_F1"] = S.groupby(["technique", "scenario"])["F1"].mean().groupby("technique").min(); T["owner"] = [WHO[k] for k in T.index]
T.round(3).to_csv(f"{OUT}/ranking_table.csv"); rank.to_csv(f"{OUT}/ranks_per_metric.csv")
win = T["score_weighted"].idxmin(); json.dump(dict(winner=win, owner=WHO[win], title=TECH_TITLE[win], weights=WEIGHTS, table=T.round(3).to_dict("index")), open(f"{OUT}/winner.json", "w"), indent=1)

# ---- figures ----
cols = dict(zip(TECHS, ["tab:blue", "tab:orange", "tab:green", "tab:red"]))
fig, ax = plt.subplots(1, 4, figsize=(18, 4.2))
for a, c, ttl in zip(ax, ["F1", "corr", "FP_per_min", "lag_ms"], ["Step-detection F1 (higher better)", "Envelope correlation with truth (higher)", "False steps per minute (lower)", "Lag of envelope, ms (lower)"]):
    piv = Ssum[c].unstack(0)[TECHS]; piv.plot.bar(ax=a, color=[cols[k] for k in TECHS], legend=(c == "F1")); a.set_title(ttl, fontsize=9); a.set_xlabel(""); a.tick_params(axis="x", labelsize=7, rotation=20)
plt.tight_layout(); plt.savefig(f"{OUT}/1_synthetic_benchmark.png", dpi=80); plt.close()
fig, ax = plt.subplots(1, 3, figsize=(15, 4))
for a, c, ttl in zip(ax, ["stride_CV", "rhythm_score", "mains_residual_pct"], ["Stride-interval CV (lower)", "Gait-rhythm score (higher)", "50 Hz residual % (lower)"]):
    R.pivot(index="recording", columns="technique", values=c)[TECHS].plot.bar(ax=a, color=[cols[k] for k in TECHS], legend=(c == "stride_CV")); a.set_title(ttl, fontsize=9); a.set_xlabel("")
plt.tight_layout(); plt.savefig(f"{OUT}/2_real_data_metrics.png", dpi=80); plt.close()
x, c, o, A = synth(200, **SCEN["S1 typical"]); fig, ax = plt.subplots(5, 1, figsize=(13, 11), sharex=True); k = slice(10000, 26000); tt = np.arange(len(x))[k]/FS
ax[0].plot(tt, A[k], color="k"); ax[0].set_title("TRUE muscle amplitude envelope (synthetic)")
for a, tech in zip(ax[1:], TECHS):
    env, _ = run_chain(tech, x); a.plot(tt, env[k]/np.percentile(env[k], 99), color=cols[tech]); a.plot(tt, A[k]/A[k].max(), color="k", alpha=.35, lw=.8)
    ev, _, _, _ = detect_steps(env[5000:]); ev += 5.0; ev = ev[(ev > tt[0]) & (ev < tt[-1])]
    for e in ev: a.axvline(e, color="r", ls="--", alpha=.5, lw=1)
    a.set_title(f"{tech} ({WHO[tech]}) - grey = truth, red dashes = detected steps", fontsize=9)
ax[-1].set_xlabel("time (s)"); plt.tight_layout(); plt.savefig(f"{OUT}/3_synthetic_envelopes.png", dpi=80); plt.close()
fig, ax = plt.subplots(len(TECHS), 1, figsize=(13, 9), sharex=True); t, xr = load("Prashant"); k = slice(int(30*FS), int(50*FS)); tt = t[k]
for a, tech in zip(ax, TECHS): a.plot(tt, store[tech][k], color=cols[tech], lw=.9); a.set_ylabel(tech); a.set_title(f"{tech} envelope on Prashant's real recording", fontsize=8)
plt.tight_layout(); plt.savefig(f"{OUT}/4_real_envelopes.png", dpi=80); plt.close()
print(T[["F1","corr","FP_per_min","lag_ms","stride_CV","rhythm_score","cat_detection","cat_responsiveness","cat_fidelity","score_weighted","score_equal","worst_scenario_F1"]].round(2).to_string()); print("WINNER:", win, WHO[win])
