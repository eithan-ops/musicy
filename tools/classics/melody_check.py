#!/usr/bin/env python3
"""Does a Suno clip actually play the melody we asked for?
Chroma-template matching: fraction of chroma energy sitting on the expected pitch class,
maximised over tempo (±15%), transposition and start offset. Baseline = scrambled melody."""
import sys, json, subprocess, numpy as np, librosa

def load(path, sr=22050):
    # ffmpeg decode to mono float (librosa's audioread may choke on m4a)
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(sr), '-'], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32), sr

def template(mel):
    t, out = 0.0, []
    for i in range(0, len(mel), 2):
        n, b = mel[i], mel[i + 1]
        out.append((t, b, (n % 12) if n else -1)); t += b
    return out, t

def match(chroma, fps, mel, bpm, tempos=None, step=0.1):
    tmpl, tot = template(mel)
    F = chroma.shape[1]; best = dict(score=0)
    tempos = tempos if tempos is not None else np.arange(bpm * .85, bpm * 1.151, bpm * .01)
    for tp in tempos:
        bs = 60 / tp; L = int(round(tot * bs * fps))
        if L >= F: continue
        # precompute per-frame pitch-class index pattern for this tempo
        idx = np.full(L, -1, dtype=int)
        for t0, dur, p in tmpl:
            a, b = int(round(t0 * bs * fps)), int(round((t0 + dur) * bs * fps))
            idx[a:b] = p
        valid = idx >= 0
        for tr in range(12):
            pcs = (idx + tr) % 12
            for off in range(0, F - L, max(1, int(fps * step))):
                seg = chroma[:, off:off + L]
                s = seg[pcs[valid], np.arange(L)[valid]].mean()
                if s > best['score']: best = dict(score=round(float(s), 3), tempo=round(float(tp), 1), tr=tr, at=round(off / fps, 2))
    return best

def analyze(path, mel, bpm):
    y, sr = load(path)
    hop = 512
    chroma = librosa.feature.chroma_stft(y=y, sr=sr, n_fft=2048, hop_length=hop, norm=1)  # L1-normalised columns
    fps = sr / hop
    best = match(chroma, fps, mel, bpm)
    mel2 = list(mel)
    for i in range(0, len(mel2), 2):
        if mel2[i]: mel2[i] = 60 + (i * 7) % 12
    base = match(chroma, fps, mel2, bpm, tempos=[bpm], step=.5)
    best['baseline'] = base['score']; best['dur'] = round(len(y) / sr, 1)
    return best

if __name__ == '__main__':
    import os; M = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'melodies.json')))
    path, key = sys.argv[1], sys.argv[2]
    print(json.dumps(analyze(path, M[key]['mel'], M[key]['bpm'])))
