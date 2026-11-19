"""BioRadio -> filtered calf EMG -> UDP to Unity (Project 9). Windows + pythonnet + BioRadioSDK.dll.
GUI: Scan / Connect / Disconnect, EMG channel + filter mode selectors, Lock calibration, Record log.
Run in PowerShell:  py bioradio_unity_bridge_v2.py        (close BioCapture first)
UDP JSON per update: channel, raw_mv, rms_mv(=envelope), env_norm(0-1), active, steps, step_event, mode, sample_count, sample_rate_hz"""
import os, json, socket, time, csv, tkinter as tk
from tkinter import ttk, messagebox
from collections import deque
import numpy as np
from emg_realtime import LiveProcessor, MODES

UDP_HOST, UDP_PORT, UPDATE_MS, WINDOW_S = "127.0.0.1", 50557, 50, 8
TO_MV = 1000.0   # VERIFY against BioCapture (SDK scaled value -> mV)
try:
    import clr
    clr.AddReference(os.path.join(os.path.dirname(os.path.abspath(__file__)), "BioRadioSDK.dll"))
    from GLNeuroTech.Devices.BioRadio import BioRadioDeviceManager
    import matplotlib; matplotlib.use("TkAgg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
except Exception as exc:
    raise SystemExit("Install pythonnet + matplotlib, check DLL. Details: %r" % exc)

root = tk.Tk(); root.title("BioRadio EMG -> Unity (Project 9)"); root.geometry("1050x720")
manager = BioRadioDeviceManager(); sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
found, device, signals, proc, fs, running = [], None, [], None, 1000.0, False
raw_buf = env_buf = None; total = 0; logf = logw = None; log_t0 = 0.0

bar = ttk.Frame(root, padding=8); bar.pack(fill="x")
dev_box = ttk.Combobox(bar, width=34, state="readonly"); dev_box.pack(side="left", padx=4)
ch_var = tk.IntVar(value=1); ttk.Label(bar, text="EMG ch").pack(side="left"); ttk.Spinbox(bar, from_=1, to=8, width=3, textvariable=ch_var).pack(side="left")
mode_box = ttk.Combobox(bar, width=30, state="readonly", values=["%s: %s" % kv for kv in MODES.items()]); mode_box.current(8); mode_box.pack(side="left", padx=6)
status = tk.StringVar(value="Scan, select device, Connect."); info = tk.StringVar(value="")
ttk.Label(root, textvariable=status, padding=4).pack(anchor="w"); ttk.Label(root, textvariable=info, padding=4, font=("Consolas", 11)).pack(anchor="w")
fig = Figure(figsize=(10, 6), dpi=90); axr = fig.add_subplot(211); axe = fig.add_subplot(212)
(line_r,) = axr.plot([], [], lw=.5, color="black"); (line_e,) = axe.plot([], [], lw=1, color="tab:blue"); (thr_line,) = axe.plot([], [], "r--", lw=.8)
axr.set_ylabel("raw (mV, offset removed)"); axe.set_ylabel("envelope (mV)"); axe.set_xlabel("time (s)")
canvas = FigureCanvasTkAgg(fig, master=root); canvas.get_tk_widget().pack(fill="both", expand=True)

def scan():
    if device: return messagebox.showinfo("Disconnect first", "Disconnect before scanning.")
    try:
        r = manager.DiscoverBluetoothDevices(); found[:] = []
        for i in range(r.Length):
            d = r[i]; found.append((str(d.DeviceId), str(d.MacId).replace(":", "").replace("-", "").upper()))
        dev_box["values"] = ["%s | %s" % x for x in found]
        if found: dev_box.current(0)
        status.set("%d device(s) found." % len(found))
    except Exception as e: status.set("Discovery failed: %s" % e)

def connect():
    global device, signals, proc, fs, running, raw_buf, env_buf, total
    if device: return
    if dev_box.current() < 0: return messagebox.showwarning("Select", "Scan and select a BioRadio.")
    cand = None
    try:
        name, mac = found[dev_box.current()]; cand = manager.GetBluetoothDevice(int(mac, 16))
        g = cand.BioPotentialSignals; n = int(g.Count)
        if n < 1: raise RuntimeError("No enabled biopotential channels (set in BioCapture).")
        fs = float(g.SamplesPerSecond); signals = [g[i] for i in range(n)]
        proc = LiveProcessor(fs, mode_box.get()[0]); cap = int(WINDOW_S*fs)
        raw_buf, env_buf, total = deque(maxlen=cap), deque(maxlen=cap), 0
        cand.StartAcquisition(); device = cand; running = True
        status.set("%s | %d ch | %.0f Hz | UDP %s:%d" % (name, n, fs, UDP_HOST, UDP_PORT)); root.after(UPDATE_MS, update)
    except Exception as e:
        if cand is not None:
            try: cand.Disconnect()
            except Exception: pass
        status.set("Connection failed: %r" % e)

def disconnect():
    global device, running
    running = False; stop_log()
    if device is not None:
        for fn in ("StopAcquisition", "Disconnect"):
            try: getattr(device, fn)()
            except Exception as e: print(fn, repr(e))
    device = None; status.set("Disconnected.")

def lock():
    if proc and proc.lock_calibration(): status.set("Calibration LOCKED (thresholds from last ~30 s of walking).")
    else: status.set("Not enough data yet - walk for ~10 s first.")
def unlock():
    if proc: proc.unlock_calibration(); status.set("Calibration auto-adapting again.")
def start_log():
    global logf, logw, log_t0
    if logf or not device: return
    name = time.strftime("emg_log_%Y%m%d_%H%M%S.csv"); logf = open(name, "w", newline=""); logw = csv.writer(logf)
    logw.writerow(["t_s", "mode", "raw_mv", "env_mv", "env_norm", "active", "steps"]); log_t0 = time.time(); status.set("Logging to " + name)
def stop_log():
    global logf, logw
    if logf: logf.close(); logf = logw = None; status.set("Log saved.")
def on_mode(_e=None):
    if proc: proc.set_mode(mode_box.get()[0]); raw_buf.clear(); env_buf.clear(); status.set("Mode -> " + mode_box.get())
mode_box.bind("<<ComboboxSelected>>", on_mode)

def update():
    global total
    if not running or device is None: return
    try:
        i = max(0, min(ch_var.get(), len(signals)) - 1)
        b = signals[i].GetScaledValueArray()
        if b is not None and len(b) > 0:
            x = np.array([float(v) for v in b]) * TO_MV
            env = proc.process(x); st = proc.update(env); total += len(x)
            raw_buf.extend(x - np.mean(x) if proc.mode == "A" else x - proc.offset); env_buf.extend(env)
            msg = dict(channel=i+1, raw_mv=float(x[-1]), rms_mv=st["env_mv"], env_norm=st["env_norm"], active=int(st["active"]),
                       steps=st["steps"], step_event=int(st["step_event"]), mode=proc.mode, sample_count=total, sample_rate_hz=fs)
            sock.sendto(json.dumps(msg).encode(), (UDP_HOST, UDP_PORT))
            if logw: logw.writerow(["%.3f" % (time.time()-log_t0), proc.mode, "%.5f" % x[-1], "%.6f" % st["env_mv"], "%.3f" % st["env_norm"], int(st["active"]), st["steps"]])
            info.set("mode %s | env %.4f mV | norm %.2f | %s | steps %d | %s" % (proc.mode, st["env_mv"], st["env_norm"], "ACTIVE" if st["active"] else "rest  ", st["steps"], "locked" if st["locked"] else ("auto-cal" if st["calibrated"] else "calibrating...")))
            r, e = np.fromiter(raw_buf, float), np.fromiter(env_buf, float); t = (np.arange(len(r)) - len(r)) / fs
            line_r.set_data(t, r); line_e.set_data(t, e)
            if proc.on_thr: thr_line.set_data([t[0], 0], [proc.on_thr, proc.on_thr])
            for a, y in ((axr, r), (axe, e)): a.set_xlim(-WINDOW_S, 0); a.set_ylim(min(y.min(), 0) * 1.1 if a is axr else 0, max(abs(y).max(), 1e-3) * 1.2)
            canvas.draw_idle()
    except Exception as ex: status.set("Read/plot error: %r" % ex); print(ex)
    if running: root.after(UPDATE_MS, update)

for lbl, cb in [("Scan", scan), ("Connect", connect), ("Disconnect", disconnect), ("Lock cal.", lock), ("Auto cal.", unlock), ("Start log", start_log), ("Stop log", stop_log)]:
    ttk.Button(bar, text=lbl, command=cb).pack(side="left", padx=2)
def close(): disconnect(); sock.close(); root.destroy()
root.protocol("WM_DELETE_WINDOW", close); root.mainloop()
