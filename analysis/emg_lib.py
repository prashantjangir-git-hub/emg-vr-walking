"""Shared helpers for the per-member and comparative analyses (data loading, clean-segment selection,
metrics, synthetic ground-truth benchmark). Needs numpy, pandas, scipy, matplotlib, PyWavelets."""
import os, sys, numpy as np, pandas as pd
from scipy import signal
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.join(HERE, "..", "bridge"))
from emg_chains import CHAINS, MEMBER_TECHNIQUE, TECH_TITLE

# Data: by default the labelled datasets in ../data are used (they contain the original raw columns).
# To use the original BioRadio CSVs instead, set DATA_DIR to their folder (raw file names below are tried first).
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "..", "data"))
FILES = {"Akshit": "akshit.csv", "Mehul": "Mehul.csv", "Naveen": "Naveen.csv", "Prashant": "prashant.csv"}
LABELLED = {n: f"{n}_labelled.csv" for n in FILES}
LABEL_COLS = ["subject", "activity", "segment_label", "step_event"]   # added by make_supplementary.py, not raw data
FS, CHANNEL, WIN_S = 1000.0, "ch1_mv", 8
MIN_RHYTHM, MAX_PEAK_SIGMA, MAX_ART_PCT, MAX_JUMP_X = 0.38, 22, 0.7, 2.5
SYN_SEED_BASE, SYN_SEEDS = 200, range(5)       # synthetic benchmark: same 4 scenarios x 5 seeds in every script
_BP = signal.butter(4, [20, 450], "band", fs=FS, output="sos"); _NT = signal.tf2sos(*signal.iirnotch(50, 30, fs=FS)); _LP5 = signal.butter(2, 5, "low", fs=FS, output="sos")

def path_of(name):
    for fn in (FILES[name], LABELLED[name]):
        p = os.path.join(DATA_DIR, fn)
        if os.path.exists(p): return p
    raise FileNotFoundError(f"No recording for {name} in {DATA_DIR} (looked for {FILES[name]} and {LABELLED[name]})")
def read_raw(name):
    d = pd.read_csv(path_of(name)); return d.drop(columns=[c for c in LABEL_COLS if c in d.columns])
def load(name):
    d = read_raw(name); x = d[CHANNEL].dropna(); return d.time_s.values[:len(x)], x.values

# ---------- clean-segment selection ----------
def score_windows(x):
    y = signal.sosfiltfilt(_NT, signal.sosfiltfilt(_BP, x)); sig = 1.4826*np.median(np.abs(y - np.median(y)))
    env = signal.sosfiltfilt(_LP5, np.abs(y)); n = int(WIN_S*FS); rows = []
    for k in range(0, len(x) - n + 1, n):
        yy, e, r = y[k:k+n], env[k:k+n], x[k:k+n]; ee = e - e.mean(); ac = np.correlate(ee, ee, "full")[len(ee)-1:]; ac /= ac[0]
        rows.append(dict(start_s=k/FS, end_s=(k+n)/FS, rhythm=ac[int(.6*FS):int(1.6*FS)].max(), peak_sigma=np.max(np.abs(yy))/sig,
                         art_pct=100*np.mean(np.abs(yy) > 8*sig), jump=np.max(np.abs(np.diff(r[::10])))))
    d = pd.DataFrame(rows)
    d["good"] = (d.rhythm >= MIN_RHYTHM) & (d.peak_sigma <= MAX_PEAK_SIGMA) & (d.art_pct <= MAX_ART_PCT) & (d.jump <= MAX_JUMP_X*d.jump.median()); return d
def runs_from(d):
    runs = []
    for _, r in d[d.good].iterrows():
        if runs and abs(runs[-1][1] - r.start_s) < 1e-6: runs[-1][1] = r.end_s
        else: runs.append([r.start_s, r.end_s])
    return [tuple(r) for r in runs]
def cut(a, runs): return [a[int(s*FS):int(e*FS)] for s, e in runs]

# ---------- run a streaming chain over a whole signal ----------
def run_chain(tech, x, batch=50):
    c = CHAINS[tech](FS); x = np.asarray(x, float) - np.mean(x[:int(FS)]); env, clean = [], []
    for i in range(0, len(x), batch):
        env.append(c.process(x[i:i+batch])); clean.append(c.last_clean)
    return np.concatenate(env), np.concatenate(clean)

# ---------- step detection on an envelope (same logic as the live processor) ----------
def detect_steps(env, refractory=0.45):
    """auto thresholds from the lowest 30% of the envelope, hysteresis, one step per rising edge"""
    base = np.sort(env)[: max(10, int(0.3*len(env)))]; on, off = base.mean() + 3*base.std(), base.mean() + 1.5*base.std()
    act, st, last, ev = np.zeros(len(env), bool), False, -1e9, []
    for i, v in enumerate(env):
        prev = st; st = (v > on) if not prev else (v > off); act[i] = st
        if st and not prev and (i/FS - last) > refractory: ev.append(i/FS); last = i/FS
    return np.array(ev), act, on, off

# ---------- metrics on real recordings (no ground truth) ----------
def real_metrics(env, clean, runs):
    E = np.concatenate(cut(env, runs)); C = np.concatenate(cut(clean, runs)); p10, p90 = np.percentile(E, 10), np.percentile(E, 90)
    iv, rh, n_st, dur = [], [], 0, 0.0
    for e, c in zip(cut(env, runs), cut(clean, runs)):
        ev, _, _, _ = detect_steps(e); n_st += len(ev); dur += len(e)/FS; iv += list(np.diff(ev))
        ee = e - e.mean(); ac = np.correlate(ee, ee, "full")[len(ee)-1:]; ac /= ac[0]; rh.append(ac[int(.6*FS):int(1.6*FS)].max())
    f, p = signal.welch(C - C.mean(), fs=FS, nperseg=2048); band = lambda lo, hi: np.trapezoid(p[(f >= lo) & (f <= hi)], f[(f >= lo) & (f <= hi)])
    iv = np.array(iv)
    return dict(burst_to_baseline=p90/(p10+1e-12), strides_per_min=n_st/dur*60, stride_CV=(iv.std()/iv.mean() if len(iv) > 2 else np.nan),
                rhythm_score=float(np.mean(rh)), mains_residual_pct=100*band(48, 52)/band(20, 450), good_seconds=dur)

# ---------- synthetic ground-truth benchmark ----------
SCEN = {"S1 typical": dict(amp=1.0, hum=1.0, spikes=3, noise=1.0), "S2 strong 50 Hz hum": dict(amp=1.0, hum=3.0, spikes=3, noise=1.0),
        "S3 motion spikes": dict(amp=1.0, hum=1.0, spikes=18, noise=1.0), "S4 weak muscle": dict(amp=0.45, hum=1.0, spikes=3, noise=1.0)}
def synth(seed, dur=60.0, amp=1.0, hum=1.0, spikes=3, noise=1.0):
    """returns x (mV), burst centre times (s), burst onset times (s), true amplitude envelope (mV)"""
    rng = np.random.default_rng(seed); n = int(dur*FS); t = np.arange(n)/FS
    centres, c = [], 1.0 + rng.uniform(0, .3)
    while c < dur - 1: centres.append(c); c += rng.normal(1.05, .08)
    centres = np.array(centres); A = 0.012*np.ones(n)*amp * 0.5               # low tonic activity
    for c in centres: A += 0.045*amp*np.exp(-0.5*((t - c)/0.085)**2)         # mV, ~300 ms bursts
    carrier = signal.sosfiltfilt(_BP, rng.standard_normal(n)); carrier /= carrier.std()
    emg = A*carrier
    drift = np.cumsum(rng.standard_normal(n)); drift = signal.sosfiltfilt(signal.butter(2, 0.15, "low", fs=FS, output="sos"), drift); drift *= 1.8/np.abs(drift).max()
    ripple = 0.08*np.sin(2*np.pi*0.95*t + rng.uniform(0, 6.28))            # stride-synchronous motion artifact
    mains = 0.03*hum*np.sin(2*np.pi*50*t + rng.uniform(0, 6.28)) + 0.004*hum*np.sin(2*np.pi*150*t)
    sens = 0.004*noise*rng.standard_normal(n)
    sp = np.zeros(n)
    for k in rng.integers(2000, n-200, size=int(spikes*dur/60)):
        L = 40; sp[k:k+L] += rng.choice([-1, 1])*rng.uniform(.3, .7)*np.exp(-np.arange(L)/8.0)*np.cos(np.arange(L)*0.6)
    x = 3.0 + drift + ripple + mains + emg + sens + sp
    onsets = np.array([ (t[A > 0.012*amp*0.5 + 0.25*0.045*amp][ (np.abs(t[A > 0.012*amp*0.5 + 0.25*0.045*amp] - c) < 0.4) ][0]) if np.any(np.abs(t[A > 0.012*amp*0.5 + 0.25*0.045*amp] - c) < 0.4) else c - 0.1 for c in centres])
    return x, centres, onsets, A

def synth_metrics(tech, x, centres, onsets, A):
    import time; t0 = time.time(); env, _ = run_chain(tech, x); rt = (time.time() - t0)/(len(x)/FS)
    a, b = int(5*FS), len(env) - int(1*FS)
    ee, aa = env[a:b], A[a:b]
    lags = np.arange(0, 301, 5); cc = [np.corrcoef(ee[l:], aa[:len(aa)-l])[0, 1] for l in lags]; corr = float(np.max(cc)); lag = int(lags[int(np.argmax(cc))])
    ev, _, _, _ = detect_steps(env[a:]); ev = ev + a/FS; ctr = centres[(centres > 5) & (centres < len(env)/FS - 1)]
    matched, used, delays = 0, set(), []
    for c, o in zip(centres, onsets):
        if not (5 < c < len(env)/FS - 1): continue
        j = [i for i, e in enumerate(ev) if (c - 0.35) <= e <= (c + 0.25) and i not in used]
        if j: used.add(j[0]); matched += 1; delays.append(ev[j[0]] - o)
    fp = len(ev) - len(used); tp = matched; fn = len(ctr) - tp
    prec = tp/max(tp + fp, 1); rec = tp/max(len(ctr), 1); f1 = 2*prec*rec/max(prec + rec, 1e-9)
    return dict(corr=corr, lag_ms=lag, F1=f1, precision=prec, recall=rec, FP_per_min=fp/((b - a)/FS/60), delay_ms=1000*float(np.median(delays)) if delays else np.nan, realtime_factor=rt)
