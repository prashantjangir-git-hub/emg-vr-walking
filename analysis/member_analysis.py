"""One team member's individual analysis: their own technique applied to their own recording (clean segments),
compared with the kit's unfiltered baseline. Outputs figures + tables to members/<Name>/ ."""
import json, os, numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy import signal
from emg_lib import *

def baseline_env(x):                         # kit baseline: no filtering, 50 ms RMS
    y = x - np.mean(x); k = np.ones(50)/50; return np.sqrt(np.convolve(y**2, k, "full")[:len(y)])

def run(name):
    tech = MEMBER_TECHNIQUE[name]; out = os.path.join(HERE, "members", name); os.makedirs(out, exist_ok=True)
    t, x = load(name); d = score_windows(x); runs = runs_from(d); d.round(3).to_csv(f"{out}/window_quality.csv", index=False)
    env, clean = run_chain(tech, x); xr = x - np.mean(x[:int(FS)]); base = baseline_env(xr)
    # ---- Fig 1: data quality + clean segment selection ----
    fig, ax = plt.subplots(2, 1, figsize=(13, 6))
    for _, r in d.iterrows(): ax[0].axvspan(r.start_s, r.end_s, color="tab:green" if r.good else "tab:red", alpha=.22)
    ax[0].plot(t, x - np.median(x), lw=.4, color="k"); ax[0].set_title(f"{name}: raw ch1 (green = clean windows used, red = rejected)"); ax[0].set_ylabel("mV")
    ax[1].bar(d.start_s + WIN_S/2, d.rhythm, width=WIN_S*.9, color=["tab:green" if g else "tab:red" for g in d.good]); ax[1].axhline(MIN_RHYTHM, ls="--", color="k")
    ax[1].set_ylabel("gait-rhythm score"); ax[1].set_xlabel("time (s)"); plt.tight_layout(); plt.savefig(f"{out}/1_data_quality.png", dpi=80); plt.close()
    # ---- Fig 2: spectrum before / after ----
    rawg = np.concatenate(cut(xr, runs)); cg = np.concatenate(cut(clean, runs)); f1, p1 = signal.welch(rawg - rawg.mean(), FS, nperseg=2048); f2, p2 = signal.welch(cg - cg.mean(), FS, nperseg=2048)
    fig, ax = plt.subplots(figsize=(9, 4.5)); ax.semilogy(f1, p1, label="raw (clean windows)"); ax.semilogy(f2, p2, label=f"after {tech}"); ax.axvline(50, color="r", alpha=.3); ax.set_xlim(0, 500)
    ax.set_xlabel("Hz"); ax.set_ylabel("PSD"); ax.legend(); ax.set_title(f"{name} - spectrum before/after ({tech})"); plt.tight_layout(); plt.savefig(f"{out}/2_spectrum.png", dpi=80); plt.close()
    # ---- Fig 3: zoom with steps ----
    s0 = runs[0][0] + 1; k = slice(int(s0*FS), int((s0 + 12)*FS)); tt = t[k]
    ev, act, on, off = detect_steps(np.concatenate(cut(env, runs[:1])) if False else env[int(runs[0][0]*FS):int(runs[0][1]*FS)])
    ev = ev + runs[0][0]; ev = ev[(ev >= s0) & (ev <= s0 + 12)]
    fig, ax = plt.subplots(3, 1, figsize=(13, 8), sharex=True)
    ax[0].plot(tt, xr[k] - np.median(xr[k]), lw=.5, color="k"); ax[0].set_title(f"{name}: raw (offset removed) - drift and hum dominate"); ax[0].set_ylabel("mV")
    ax[1].plot(tt, 1000*clean[k], lw=.5); ax[1].set_ylabel("uV"); ax[1].set_title(f"cleaned signal ({tech})")
    ax[2].plot(tt, base[k]/np.percentile(base[k], 99), lw=.8, color="gray", label="kit baseline (no filter, 50 ms RMS)"); ax[2].plot(tt, env[k]/np.percentile(env[k], 99), lw=1.4, label=f"{tech} envelope")
    for e in ev: ax[2].axvline(e, color="r", alpha=.5, ls="--", lw=1)
    ax[2].set_title("envelope (normalised); red dashes = detected steps"); ax[2].legend(fontsize=8); ax[2].set_xlabel("time (s)"); plt.tight_layout(); plt.savefig(f"{out}/3_envelope_and_steps.png", dpi=80); plt.close()
    # ---- tables ----
    own = real_metrics(env, clean, runs); bas = real_metrics(base, xr - np.mean(xr), runs)
    syn = []
    for sc, kw in SCEN.items():
        for seed in SYN_SEEDS: m = synth_metrics(tech, *synth(SYN_SEED_BASE + seed, **kw)); m.update(scenario=sc, seed=seed); syn.append(m)   # same signals as comparative_analysis.py
    S = pd.DataFrame(syn); S.round(3).to_csv(f"{out}/synthetic_results.csv", index=False)
    summ = dict(person=name, technique=tech, title=TECH_TITLE[tech], recording_s=round(t[-1], 1), good_s=round(own["good_seconds"], 1), good_pct=round(100*own["good_seconds"]/t[-1], 1),
                own={k: round(float(v), 3) for k, v in own.items()}, baseline={k: round(float(v), 3) for k, v in bas.items()},
                synthetic_mean=S.groupby("scenario")[["corr", "lag_ms", "F1", "FP_per_min"]].mean().round(3).to_dict("index"),
                synthetic_overall=S[["corr", "lag_ms", "F1", "precision", "recall", "FP_per_min", "delay_ms", "realtime_factor"]].mean().round(3).to_dict())
    json.dump(summ, open(f"{out}/summary.json", "w"), indent=1); print(name, tech, json.dumps(summ["own"]), "| synth F1 %.2f corr %.2f lag %d" % (summ["synthetic_overall"]["F1"], summ["synthetic_overall"]["corr"], summ["synthetic_overall"]["lag_ms"]))
    return summ
