"""Four streaming (causal, real-time capable) EMG processing techniques - one per team member.
Each chain: process(x_mv) -> envelope (mV-like amplitude); the cleaned signal before the envelope stage is kept in .last_clean.
  IIR   (Akshit)   Butterworth band-pass + IIR notch + full-wave rectification + 3 Hz low-pass
  ADFIR (Mehul)    FIR (Hamming) band-pass + adaptive LMS 50 Hz canceller + 200 ms moving RMS
  WAVE  (Naveen)   IIR notch + wavelet (db4) denoising on sliding blocks + rectification + 3 Hz low-pass
  TKEO  (Prashant) Butterworth band-pass + notch + Teager-Kaiser energy operator + 3 Hz low-pass
"""
import warnings
import numpy as np
from scipy import signal
warnings.filterwarnings("ignore", message="Level value")

def _sos_bp(fs): return signal.butter(4, [20, min(450, 0.45*fs)], "band", fs=fs, output="sos")
def _sos_n(fs, f0=50.0): return signal.tf2sos(*signal.iirnotch(f0, 30, fs=fs))
def _sos_lp(fs, fc=3.0): return signal.butter(2, fc, "low", fs=fs, output="sos")

class _SOS:
    """stateful cascade of second-order sections"""
    def __init__(self, sos): self.sos = sos; self.z = np.zeros((sos.shape[0], 2))
    def __call__(self, x):
        y, self.z = signal.sosfilt(self.sos, x, zi=self.z); return y

class IIRChain:
    name = "IIR"
    def __init__(self, fs=1000.0, mains=50.0):
        self.bp, self.nt, self.lp = _SOS(_sos_bp(fs)), _SOS(_sos_n(fs, mains)), _SOS(_sos_lp(fs)); self.last_clean = None
    def process(self, x):
        y = self.nt(self.bp(np.asarray(x, float))); self.last_clean = y
        return np.maximum(self.lp(np.abs(y)), 0)

class ADFIRChain:
    name = "ADFIR"
    def __init__(self, fs=1000.0, mains=50.0, taps=151, mu=0.01):
        self.fs, self.f0, self.mu = fs, mains, mu
        self.b = signal.firwin(taps, [20, min(450, 0.45*fs)], pass_zero=False, window="hamming", fs=fs)
        self.zi = np.zeros(taps - 1); self.w = np.zeros(2); self.n = 0; self.hist = np.zeros(0); self.nrms = int(0.2*fs); self.last_clean = None
    def process(self, x):
        x = np.asarray(x, float)
        y, self.zi = signal.lfilter(self.b, 1.0, x, zi=self.zi)
        t = (self.n + np.arange(len(y))) / self.fs; self.n += len(y)
        r1, r2 = np.sin(2*np.pi*self.f0*t), np.cos(2*np.pi*self.f0*t); out = np.empty_like(y); w1, w2 = self.w
        for i in range(len(y)):                      # normalised LMS (|r|^2 = 1)
            e = y[i] - (w1*r1[i] + w2*r2[i]); w1 += self.mu*e*r1[i]; w2 += self.mu*e*r2[i]; out[i] = e
        self.w = np.array([w1, w2]); self.last_clean = out
        sq = np.concatenate([self.hist, out**2]); c = np.cumsum(np.insert(sq, 0, 0.0)); idx = np.arange(1, len(sq)+1)
        w = np.minimum(idx, self.nrms); env = np.sqrt((c[idx] - c[idx - w]) / w)[len(self.hist):]; self.hist = sq[-(self.nrms-1):]
        return env

class WaveChain:
    name = "WAVE"
    def __init__(self, fs=1000.0, mains=50.0, block=512, level=5, wavelet="db4"):
        import pywt; self.pywt = pywt
        self.nt, self.lp = _SOS(_sos_n(fs, mains)), _SOS(_sos_lp(fs)); self.block, self.level, self.wavelet = block, level, wavelet
        self.buf = np.zeros(0); self.last_clean = None
    def _denoise(self, seg):
        pw = self.pywt; c = pw.wavedec(seg, self.wavelet, level=self.level, mode="symmetric")
        c[0] = np.zeros_like(c[0])                                    # drop approximation (< ~15 Hz: drift, motion artifact)
        sigma = np.median(np.abs(c[-1])) / 0.6745; thr = sigma*np.sqrt(2*np.log(len(seg)))
        c[-1] = pw.threshold(c[-1], thr, "soft")                      # finest band is noise-dominated
        for i in range(1, len(c)-1): c[i] = pw.threshold(c[i], 0.35*thr, "soft")   # mild shrinkage elsewhere
        return pw.waverec(c, self.wavelet, mode="symmetric")[:len(seg)]
    def process(self, x):
        x = self.nt(np.asarray(x, float)); n = len(x)
        self.buf = np.concatenate([self.buf, x])[-(self.block + n):]
        seg = self.buf if len(self.buf) >= 64 else np.pad(self.buf, (64-len(self.buf), 0))
        den = self._denoise(seg)[-n:]; self.last_clean = den
        return np.maximum(self.lp(np.abs(den)), 0)

class TKEOChain:
    name = "TKEO"
    def __init__(self, fs=1000.0, mains=50.0):
        self.bp, self.nt, self.lp = _SOS(_sos_bp(fs)), _SOS(_sos_n(fs, mains)), _SOS(_sos_lp(fs)); self.tail = np.zeros(2); self.last_clean = None
    def process(self, x):
        y = self.nt(self.bp(np.asarray(x, float))); self.last_clean = y
        z = np.concatenate([self.tail, y]); self.tail = z[-2:]
        psi = z[1:-1]**2 - z[:-2]*z[2:]                      # psi[n] = x[n]^2 - x[n-1]x[n+1]  (one-sample delay)
        e = self.lp(np.abs(psi)); return np.sqrt(np.maximum(e, 0))

CHAINS = {"IIR": IIRChain, "ADFIR": ADFIRChain, "WAVE": WaveChain, "TKEO": TKEOChain}
MEMBER_TECHNIQUE = {"Akshit": "IIR", "Mehul": "ADFIR", "Naveen": "WAVE", "Prashant": "TKEO"}
TECH_TITLE = {"IIR": "Classical IIR chain (Butterworth band-pass + notch + rectify + low-pass)",
              "ADFIR": "FIR band-pass + adaptive LMS mains canceller + moving RMS",
              "WAVE": "Wavelet (db4) denoising + rectify + low-pass",
              "TKEO": "Teager-Kaiser energy operator + low-pass"}
