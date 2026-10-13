import sys, json, numpy as np, librosa
from melody_check import load, match
import os; M = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'melodies.json')))
path = sys.argv[1]; bpm = float(sys.argv[2]) if len(sys.argv) > 2 else None
y, sr = load(path); hop = 512
chroma = librosa.feature.chroma_stft(y=y, sr=sr, n_fft=2048, hop_length=hop, norm=1); fps = sr / hop
res = {}
for k, d in M.items():
    b = bpm or d['bpm']
    res[k] = match(chroma, fps, d['mel'], b)
for k, v in sorted(res.items(), key=lambda x: -x[1]['score']): print(k, v)
