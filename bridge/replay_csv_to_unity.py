"""Replay a recorded CSV to Unity over UDP in real time - test Unity WITHOUT the BioRadio.
  python replay_csv_to_unity.py prashant.csv --mode E --speed 1.0"""
import argparse, json, socket, time, numpy as np, pandas as pd
from emg_realtime import LiveProcessor
ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--mode", default="I")
ap.add_argument("--channel", default="ch1_mv"); ap.add_argument("--speed", type=float, default=1.0)
ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--port", type=int, default=50557); ap.add_argument("--loop", action="store_true")
a = ap.parse_args()
x = pd.read_csv(a.csv)[a.channel].dropna().values; fs = 1000.0; B = 50
lp = LiveProcessor(fs, a.mode); s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); t0 = time.time(); i = 0; n = 0
print("Replaying", a.csv, "mode", a.mode, "-> udp", a.host, a.port)
while True:
    if i + B > len(x):
        if not a.loop: break
        i = 0
    st = lp.update(lp.process(x[i:i+B])); i += B; n += B
    msg = dict(channel=1, raw_mv=float(x[i-1]), rms_mv=st["env_mv"], env_norm=st["env_norm"], active=int(st["active"]),
               steps=st["steps"], step_event=int(st["step_event"]), mode=a.mode, sample_count=n, sample_rate_hz=fs)
    s.sendto(json.dumps(msg).encode(), (a.host, a.port))
    time.sleep(max(0, t0 + n/fs/a.speed - time.time()))
print("done; steps detected:", lp.steps)
