"""Builds the labelled datasets (one per team member) for the supplementary material.
Each file keeps the original raw columns and adds: subject, activity, segment_label (clean / rejected / unassessed),
step_event (1 at each step detected by the TKEO pipeline inside clean segments)."""
import os, numpy as np, pandas as pd
from emg_lib import *
OUT = os.path.join(HERE, "..", "data"); os.makedirs(OUT, exist_ok=True)
summ = []
for name in FILES:
    raw = read_raw(name); t, x = load(name); d = score_windows(x); runs = runs_from(d)
    n = len(raw); label = np.array(["unassessed"] * n, dtype=object)
    for _, r in d.iterrows(): label[int(r.start_s*FS):int(r.end_s*FS)] = "clean" if r.good else "rejected"
    env, _ = run_chain("TKEO", x); step = np.zeros(n, int); nsteps = 0
    for s, e in runs:
        ev, _, _, _ = detect_steps(env[int(s*FS):int(e*FS)])
        for v in ev: step[int(s*FS) + int(v*FS)] = 1
        nsteps += len(ev)
    out = raw.copy(); out.insert(0, "subject", name); out.insert(1, "activity", "overground_walking")
    out["segment_label"] = label; out["step_event"] = step
    fn = f"{name}_labelled.csv"; out.to_csv(os.path.join(OUT, fn), index=False)
    # duration_s = length of the ch1 EMG signal (same definition as the report; ch1 is blank in the last rows of some files)
    summ.append(dict(subject=name, file=fn, rows=n, duration_s=round(t[-1], 1), clean_s=round(sum(e-s for s, e in runs), 1), rejected_s=round(float((label == 'rejected').sum())/FS, 1), steps_in_clean=nsteps))
S = pd.DataFrame(summ); print(S.to_string()); S.to_csv(os.path.join(OUT, "dataset_summary.csv"), index=False)
rows = "\n".join(f"| {r.subject} | `{r.file}` | {r.duration_s} | {r.clean_s} | {r.rejected_s} | {r.steps_in_clean} |" for r in S.itertuples())
open(os.path.join(OUT, "README_datasets.md"), "w").write(f"""# Supplementary material: labelled EMG datasets (Project 9)

Four datasets, one per team member (4 members = 4 datasets). Overground walking, calf EMG of the dominant leg recorded with a BioRadio; channel 1 (ch1_mv) is the calf EMG, channels 2-4 are unused (flat DC lines). Sampling rate 1000 Hz.

| Subject | File | EMG duration (s) | Clean (s) | Rejected (s) | Steps found in clean part |
|---|---|---|---|---|---|
{rows}

## Columns
| Column | Meaning |
|---|---|
| subject | team member who was recorded |
| activity | activity label (`overground_walking` for the whole recording) |
| sample, time_s | sample index and time in seconds (original) |
| ch1_mv ... ch4_mv | raw signal in mV (original, unfiltered; ch1 = calf EMG). ch1/ch2 are blank at the very end of some files (original device output) |
| segment_label | quality label of each 8 s window: `clean` (used for analysis), `rejected` (spikes, baseline jumps or no clear stride rhythm), `unassessed` (last incomplete window) |
| step_event | 1 at the sample where the TKEO pipeline detected a step (calf burst = one stride), only inside `clean` windows; 0 elsewhere |

## How labels were made
8 s windows were kept as `clean` when they showed a clear stride rhythm (envelope autocorrelation >= 0.38 at 0.6-1.6 s lag), no spike (largest sample <= 22x noise sigma, <= 0.7% of samples beyond 8 sigma) and no fast baseline jump. Steps come from the Teager-Kaiser pipeline with adaptive thresholds. The step labels are algorithmic, not hand-annotated: no video or foot-switch ground truth was available.
""")
