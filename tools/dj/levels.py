import sys, numpy as np, subprocess, os
def load(p, sr=32000):
    raw = subprocess.run(['ffmpeg','-v','error','-i',p,'-f','f32le','-ac','1','-ar',str(sr),'-'],capture_output=True).stdout
    return np.frombuffer(raw,dtype=np.float32)
d=sys.argv[1]; bpm=float(sys.argv[2]); ph=float(sys.argv[3]); nb=int(sys.argv[4]) if len(sys.argv)>4 else 40
sr=32000; bar=4*60/bpm
names=[f for f in sorted(os.listdir(d)) if f.endswith('.wav')]
S={f.split(' ',1)[1][:-4]:load(os.path.join(d,f)) for f in names}
def rms(y): return float(np.sqrt(np.mean(y*y)+1e-12))
tot={k:rms(v) for k,v in S.items()}; ref=max(tot.values())
print('bar  '+'  '.join(k[:6].rjust(6) for k in S))
for b in range(0,nb,2):
    a=int((ph+b*bar)*sr); e=int((ph+(b+2)*bar)*sr)
    if e>len(S['Drums']): break
    print('%3d  '%b+'  '.join(('%6.1f'%(20*np.log10(rms(v[a:e])/ref+1e-9))) for k,v in S.items()))
