#!/usr/bin/env python3
"""feel[k]: how much the audition mix changes (mean |Δ log-mel dB|) when one stem is k sixteenths late (circular)."""
import numpy as np, librosa, subprocess, json, sys, os

def load_mono(path, sr=32000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-'], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

def logmel(y, sr):
    S = librosa.feature.melspectrogram(y=y, sr=sr, n_fft=1024, hop_length=256, n_mels=48, power=2.0)
    return librosa.power_to_db(S, ref=1.0, top_db=80)

def feel_arrays(stems, sr, bpm, U, judged_gain=1.5, other_gain=.55):
    """stems: dict role -> mono array (all same length = loop). Returns dict role -> list of U floats."""
    unit = int(round(15 / bpm * sr))
    n = min(len(v) for v in stems.values())
    out = {}
    for role, y in stems.items():
        if role == 'drums': continue
        others = sum(v[:n] * (1 if r == 'drums' else other_gain) for r, v in stems.items() if r != role)
        base = others + y[:n] * judged_gain
        M0 = logmel(base, sr)
        arr = [0.0]
        for k in range(1, U):
            ys = np.roll(y[:n], k * unit)
            Mk = logmel(others + ys * judged_gain, sr)
            arr.append(float(np.mean(np.abs(Mk - M0))))
        out[role] = arr
    return out

if __name__ == '__main__':
    # calibration against an existing track
    import glob, os
    d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tracks', 'index.json')))
    t = [x for x in d['tracks'] if x['id'] == sys.argv[1]][0]
    base = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tracks', t['id']) + '/'
    stems = {s['role']: load_mono(base + s['file']) for s in t['stems']}
    U = t['bars'] * t['bpb'] * 4
    mine = feel_arrays(stems, 32000, t['bpm'], U)
    for s in t['stems']:
        if 'feel' not in s: continue
        a, b = np.array(s['feel'][1:]), np.array(mine[s['role']][1:])
        k = float(np.dot(a, b) / np.dot(b, b))
        print(s['role'], 'stored max %.2f' % a.max(), 'mine max %.2f' % b.max(), 'scale %.2f' % k, 'corr %.2f' % np.corrcoef(a, b)[0, 1])
