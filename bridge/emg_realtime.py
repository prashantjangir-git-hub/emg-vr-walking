"""Streaming (causal) EMG processor for Project 9. Pure Python/numpy/scipy - no hardware needed.
Modes:  A raw 50 ms RMS (kit baseline) | B BP+rect+5 Hz LP | C BP+notch+rect+3 Hz LP
        D BP+notch+200 ms RMS          | E D + artifact clipping (6 sigma)
Feed it raw ch1 samples in mV; it returns the envelope, a 0-1 normalised value, an
activation flag (with hysteresis) and a step counter (one calf burst = one stride)."""
import numpy as np
from collections import deque
from scipy import signal
from emg_chains import CHAINS

MODES = {"A": "No filter, 50 ms RMS (kit)", "B": "BP + rect + 5 Hz LP", "C": "BP + notch + rect + 3 Hz LP",
         "D": "BP + notch + 200 ms RMS", "E": "D + artifact clip",
         "F": "IIR chain (Akshit)", "G": "FIR + adaptive LMS + RMS (Mehul)", "H": "Wavelet denoise (Naveen)", "I": "TKEO (Prashant) - BEST, default"}
CHAIN_MODES = {"F": "IIR", "G": "ADFIR", "H": "WAVE", "I": "TKEO"}

class LiveProcessor:
    def __init__(self, fs=1000.0, mode="I", mains_hz=50.0):
        self.fs, self.mains = float(fs), mains_hz
        self.sos_bp = signal.butter(4, [20, min(450, 0.45*fs)], "band", fs=fs, output="sos")
        self.sos_n = signal.tf2sos(*signal.iirnotch(mains_hz, 30, fs=fs))
        self.sos_lp = {"B": signal.butter(2, 5, "low", fs=fs, output="sos"), "C": signal.butter(2, 3, "low", fs=fs, output="sos")}
        self.locked = False
        self.set_mode(mode)

    def set_mode(self, mode):
        self.mode = mode
        self.chain = CHAINS[CHAIN_MODES[mode]](self.fs, self.mains) if mode in CHAIN_MODES else None
        self.z_bp = np.zeros((self.sos_bp.shape[0], 2)); self.z_n = np.zeros((self.sos_n.shape[0], 2))
        self.z_lp = {k: np.zeros((v.shape[0], 2)) for k, v in self.sos_lp.items()}
        self.hist = np.zeros(0); self.offset = None; self.sigma = None
        self.buf = deque(maxlen=int(30*self.fs/10))      # last 30 s envelope, decimated x10
        self.on_thr = None; self.off_thr = None; self.ref_max = None
        self.active = False; self.steps = 0; self.last_step_t = -1e9; self.t = 0.0; self.warm = 0

    # --- per-batch processing ---
    def process(self, x_mv):
        x = np.asarray(x_mv, float)
        if x.size == 0: return np.zeros(0)
        if self.offset is None: self.offset = float(np.mean(x))
        x = x - self.offset
        if self.chain is not None: return np.maximum(self.chain.process(x), 0)     # modes F-I: member techniques
        n_rms = {"A": int(0.05*self.fs), "D": int(0.2*self.fs), "E": int(0.2*self.fs)}.get(self.mode)
        if self.mode == "A":
            y = x - np.mean(x)
        else:
            y, self.z_bp = signal.sosfilt(self.sos_bp, x, zi=self.z_bp)
            if self.mode in ("C", "D", "E"): y, self.z_n = signal.sosfilt(self.sos_n, y, zi=self.z_n)
            if self.mode == "E":
                if self.sigma is None: self.sigma = max(np.std(y), 1e-6)
                lim = 6*self.sigma; y = np.clip(y, -lim, lim)
                self.sigma = 0.999*self.sigma + 0.001*np.std(y)          # slow robust-ish update (post-clip)
        if n_rms:                                   # causal moving RMS using history
            sq = np.concatenate([self.hist, y**2]); c = np.cumsum(np.insert(sq, 0, 0.0))
            w = np.minimum(np.arange(1, len(sq)+1), n_rms)
            idx = np.arange(1, len(sq)+1)
            env = np.sqrt((c[idx] - c[idx - w]) / w)[len(self.hist):]
            self.hist = sq[-(n_rms-1):] if n_rms > 1 else np.zeros(0)
        else:
            r = np.abs(y); env, self.z_lp[self.mode] = signal.sosfilt(self.sos_lp[self.mode], r, zi=self.z_lp[self.mode])
        return env

    # --- thresholds / state ---
    def _auto_thresholds(self):
        e = np.fromiter(self.buf, float)
        if len(e) < int(5*self.fs/10): return
        base = np.sort(e)[: max(10, int(0.3*len(e)))]
        self.on_thr = base.mean() + 3*base.std(); self.off_thr = base.mean() + 1.5*base.std()
        self.ref_max = max(np.percentile(e, 95), self.on_thr*1.5)

    def lock_calibration(self):               # call after ~10-20 s of normal walking
        self._auto_thresholds(); self.locked = self.on_thr is not None
        return self.locked
    def unlock_calibration(self): self.locked = False

    def update(self, env):
        """env: envelope samples from process(). Returns dict for UDP / Unity."""
        dt = 1.0/self.fs
        self.buf.extend(env[::10]); self.warm += 1
        if not self.locked and self.warm % 20 == 0: self._auto_thresholds()
        step_event = False
        if self.on_thr is not None:
            for v in env:
                self.t += dt
                prev = self.active
                self.active = (v > self.on_thr) if not prev else (v > self.off_thr)
                if self.active and not prev and (self.t - self.last_step_t) > 0.45:
                    self.steps += 1; self.last_step_t = self.t; step_event = True
        else: self.t += dt*len(env)
        cur = float(env[-1])
        norm = 0.0 if self.on_thr is None else float(np.clip((cur - self.on_thr)/max(self.ref_max - self.on_thr, 1e-9), 0, 1))
        return dict(env_mv=cur, env_norm=norm, active=bool(self.active), steps=self.steps, step_event=step_event,
                    calibrated=self.on_thr is not None, locked=self.locked, mode=self.mode)
