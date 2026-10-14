import sys, numpy as np, librosa, subprocess, os
def load(p, sr=32000):
    raw = subprocess.run(['ffmpeg','-v','error','-i',p,'-f','f32le','-ac','1','-ar',str(sr),'-'],capture_output=True).stdout
    return np.frombuffer(raw,dtype=np.float32)
d=sys.argv[1]; guess=float(sys.argv[2]); sr=32000; fps=sr/256
y=load(os.path.join(d,[f for f in os.listdir(d) if 'Drums' in f][0]))
o=librosa.onset.onset_strength(y=y,sr=sr,hop_length=256); ac=librosa.autocorrelate(o)
best=[]
for bpm in np.arange(guess-8,guess+8,.25):
    lag=60/bpm*fps*4; i=int(lag); f=lag-i; best.append((float(ac[i]*(1-f)+ac[i+1]*f)/ac[0],float(bpm)))
best.sort(reverse=True); print(d, [(round(v,3),b) for v,b in best[:3]])
