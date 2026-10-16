#!/usr/bin/env python3
"""Give a DJ loop a real beat.
   The loop is cut from the intro, where Suno keeps the drums light (hats, no kick) 8-15 dB under the band — so the player
   has no clock to judge the other parts against, and a shifted synth "just sounds like noise". This lays a four-on-the-floor
   house kick under the loop drums, and under the same bars of evolve.m4a up to the bar where the production's own kick
   arrives (measured from the low band), so the full track still continues seamlessly. band.json and the feel arrays are updated.
usage: kick_in.py <track_id> [--force] [--clap] [--level DB]   (default level: kick RMS 2 dB under the rest of the loop)
       kick_in.py --check <track_id>   just print whether the loop needs it"""
import sys, os, json, base64, subprocess, numpy as np, librosa
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.abspath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(HERE, '..', 'classics'))
from feel import feel_arrays, load_mono
SR = 32000; SR_EV = 44100; HOP = 256

def load(path, sr, ch=1):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', str(ch), '-ar', str(sr), '-'], capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32).copy(); return a if ch == 1 else a.reshape(-1, 2).T.copy()
def rms(y): return float(np.sqrt(np.mean(y * y) + 1e-12))
def db(a, b): return 20 * np.log10((a + 1e-9) / (b + 1e-9))

def kick_drum(sr, f0=165., f1=48., dur=.42):
    """one house kick: a sine sweeping down, a tight attack, a soft click on top"""
    n = int(sr * dur); t = np.arange(n) / sr
    f = f1 + (f0 - f1) * np.exp(-t / .028); ph = 2 * np.pi * np.cumsum(f) / sr
    env = np.exp(-t / .13) * (1 - np.exp(-t / .0008))
    body = np.sin(ph) * env
    click = (np.random.RandomState(7).randn(n) * np.exp(-t / .0025)) * .25
    y = np.tanh(1.6 * (body + click)) / np.tanh(1.6)
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)

def clap_hit(sr, dur=.25):
    n = int(sr * dur); t = np.arange(n) / sr; r = np.random.RandomState(3).randn(n)
    env = sum(np.exp(-np.maximum(0, t - d) / .012) * (t >= d) for d in (0, .011, .022)) + np.exp(-t / .09) * (t >= .03)
    y = r * env; b, a = butter_bp(sr);
    from scipy.signal import lfilter; y = lfilter(b, a, y)
    return (y / (np.max(np.abs(y)) + 1e-9)).astype(np.float32)
def butter_bp(sr):
    from scipy.signal import butter; return butter(2, [900 / (sr / 2), 5500 / (sr / 2)], btype='band')

def layer(n, sr, bpm, bpb, hits, sample, until=None, vel=1.0):
    """place sample on the given beats (fractions of a bar) over n samples; until = stop at this sample index"""
    out = np.zeros(n, np.float32); bar = bpb * 60 / bpm * sr; stop = n if until is None else until
    i = 0
    while True:
        base = i * bar
        if base >= stop: break
        for h in hits:
            p = int(round(base + h * 60 / bpm * sr))
            if p >= stop: break
            m = min(len(sample), n - p)
            if m > 0: out[p:p + m] += sample[:m] * vel
        i += 1
    return out

def loop_kick_share(d, bpm):
    S = np.abs(librosa.stft(d, n_fft=2048, hop_length=HOP)) ** 2; f = librosa.fft_frequencies(sr=SR, n_fft=2048)
    low = S[(f >= 40) & (f <= 120)].sum(0); share = float(low.sum() / (S.sum() + 1e-12))
    on = np.maximum(0, np.diff(np.sqrt(low), prepend=0)); on -= on.mean(); e = np.dot(on, on) + 1e-9; fps = SR / HOP; bs = 60 / bpm * fps
    pulse = max(float(np.dot(on, np.roll(on, int(round(bs)))) / e), float(np.dot(on, np.roll(on, int(round(2 * bs)))) / e))
    return share, pulse

def real_kick_bar(ev, bpm, bpb, L48):
    """first bar of the production whose low band is at least half of the track's loudest low band: the real kick is in"""
    m = ev.mean(axis=0); S = np.abs(librosa.stft(m, n_fft=2048, hop_length=512)) ** 2; f = librosa.fft_frequencies(sr=SR_EV, n_fft=2048)
    low = np.sqrt(S[(f >= 40) & (f <= 120)].sum(0)); fpb = bpb * 60 / bpm * SR_EV / 512; nb = int(len(low) / fpb)
    be = np.array([low[int(i * fpb):int((i + 1) * fpb)].mean() for i in range(nb)]); ref = np.percentile(be, 90)
    for i, v in enumerate(be):
        if v >= ref * .5 and be[i:i + 2].min() >= ref * .4: return i
    return nb

def b64u8(v): return base64.b64encode(np.clip(np.round(v * 100), 0, 100).astype(np.uint8).tobytes()).decode()
def env_rate(y, sr, rate):
    hop = int(round(sr / rate)); n = len(y) // hop; return np.sqrt(np.mean(y[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12)

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]; flags = [a for a in sys.argv[1:] if a.startswith('--')]
    tid = args[0]; level = -2.0
    for fl in flags:
        if fl.startswith('--level'): level = float(fl.split('=')[1]) if '=' in fl else float(args[1])
    tdir = os.path.join(ROOT, 'tracks', tid); entry = json.load(open(os.path.join(tdir, 'entry.json')))
    bpm, bpb, bars = entry['bpm'], entry['bpb'], entry['bars']
    ys = {s['role']: load_mono(os.path.join(tdir, s['file']), SR) for s in entry['stems']}
    n = min(len(v) for v in ys.values()); ys = {k: v[:n] for k, v in ys.items()}
    d = ys['drums']; rest = sum(v for k, v in ys.items() if k != 'drums')
    share, pulse = loop_kick_share(d, bpm)
    need = share < .15 or pulse < .3
    print('%s: drums %.1f dB vs rest, kick share %.2f, kick pulse %.2f -> %s' % (tid, db(rms(d), rms(rest)), share, pulse, 'needs a kick' if need else 'has a kick'), file=sys.stderr)
    if '--check' in flags: return
    if not need and '--force' not in flags: print('skipped (use --force)', file=sys.stderr); return
    if entry.get('kick_added') and '--force' not in flags: print('already done', file=sys.stderr); return

    # --- the layer, level-matched to the rest of the loop
    k32 = kick_drum(SR); hits = [i for i in range(bpb)]
    lay = layer(n, SR, bpm, bpb, hits, k32)
    if '--clap' in flags: lay += layer(n, SR, bpm, bpb, [1, 3] if bpb == 4 else [bpb - 1], clap_hit(SR), vel=.55)
    g = rms(rest) * 10 ** (level / 20) / (rms(lay) + 1e-9)
    newd = d + lay * g
    peak = float(np.max(np.abs(newd)))
    if peak > .97: g *= .97 / peak; newd = d + lay * g; print('kick trimmed for headroom', file=sys.stderr)
    print('kick at %.1f dB vs rest (gain %.2f), new drums %.1f dB vs rest' % (db(rms(lay * g), rms(rest)), g, db(rms(newd), rms(rest))), file=sys.stderr)
    fade = int(SR * .003); ramp = np.linspace(0, 1, fade, dtype=np.float32); newd[:fade] *= ramp; newd[-fade:] *= ramp[::-1]
    raw = (np.clip(newd, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', '-c:a', 'flac', os.path.join(tdir, 'drums.flac')], input=raw, check=True)

    # --- evolve: same layer from the loop start up to the bar where the real kick arrives
    evp = os.path.join(tdir, entry['evolve']['file']); ev = load(evp, SR_EV, 2); T = ev.shape[1]
    L48 = int(round(n / SR * SR_EV)); stop_bar = real_kick_bar(ev, bpm, bpb, L48)
    # where does the loop sit in evolve? cross-correlate the loop drums with the first two loops of evolve (the app does the same)
    dr = librosa.resample(d, orig_sr=SR, target_sr=SR_EV); seg = ev.mean(axis=0)[:min(T, 2 * L48 + SR_EV)]
    best, lag = -1, 0
    for l in range(0, min(len(seg) - len(dr), int(SR_EV * .5)), 8):
        c = float(np.dot(seg[l:l + len(dr)], dr));
        if c > best: best, lag = c, l
    stop = min(T, int(round(stop_bar * bpb * 60 / bpm * SR_EV)) + lag)
    print('real kick from bar %d (%.1fs); kick layer runs %.1fs, evolve lag %d samples' % (stop_bar, stop_bar * bpb * 60 / bpm, stop / SR_EV, lag), file=sys.stderr)
    if stop > lag + 1000:
        k44 = kick_drum(SR_EV); lay44 = layer(T - lag, SR_EV, bpm, bpb, hits, k44, until=stop - lag)
        if '--clap' in flags: lay44 += layer(T - lag, SR_EV, bpm, bpb, [1, 3] if bpb == 4 else [bpb - 1], clap_hit(SR_EV), until=stop - lag, vel=.55)
        # the loop in evolve is the mix (rest+drums at build gain .9/peak); match the layer to the loop's own level in evolve
        ev_loop = ev[:, lag:lag + L48].mean(axis=0); g44 = rms(ev_loop) * 10 ** ((level - 1.0) / 20) / (rms(lay44[:L48]) + 1e-9)
        ev[:, lag:] += lay44[None, :] * g44
        pk = float(np.max(np.abs(ev)));
        if pk > .98: ev *= .98 / pk
        raw = (np.clip(ev.T, -1, 1) * 32767).astype(np.int16).tobytes()
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 's16le', '-ar', str(SR_EV), '-ac', '2', '-i', '-', '-c:a', 'aac', '-b:a', '128k', evp], input=raw, check=True)
        # band.json: the drummer plays from bar one now
        bp = os.path.join(tdir, entry['evolve']['band']); band = json.load(open(bp)); rate = band['rate']
        e = env_rate(lay44 * g44, SR_EV, rate); e = e / (np.percentile(e, 97) + 1e-9) * .85
        cur = np.frombuffer(base64.b64decode(band['core']['drums']), dtype=np.uint8).astype(float) / 100
        m = min(len(cur), len(e)); merged = cur.copy(); merged[:m] = np.maximum(cur[:m], np.clip(e[:m], 0, 1))
        band['core']['drums'] = b64u8(merged); json.dump(band, open(bp, 'w'), ensure_ascii=False, separators=(',', ':'))

    # --- feel arrays change a little with a louder clock; recompute and write entry.json + index.json
    ys['drums'] = newd; U = bars * bpb * 4; feel = feel_arrays(ys, SR, bpm, U)
    for s in entry['stems']:
        if s['role'] in feel: s['feel'] = [round(v * 1.1, 2) for v in feel[s['role']]]
        # a bass or shaker the kick now masks joins the drums from the start instead of disappearing from the loop (same rule as build_dj)
        if s['role'] in ('bass', 'perc') and 'feel' in s and max(s['feel'][1:]) < 1.5 and not s.get('auto'): s['auto'] = True; print(s['role'] + ' is now auto (feel %.2f)' % max(s['feel'][1:]), file=sys.stderr)
    entry['kick_added'] = True; entry['v'] = int(entry.get('v') or 1) + 1  # stems are cached as immutable: a new version gets a new ?v= URL
    json.dump(entry, open(os.path.join(tdir, 'entry.json'), 'w'), ensure_ascii=False, indent=1)
    ip = os.path.join(ROOT, 'tracks', 'index.json'); idx = json.load(open(ip))
    for i, t in enumerate(idx['tracks']):
        if t['id'] == tid: idx['tracks'][i] = entry
    json.dump(idx, open(ip, 'w'), ensure_ascii=False, indent=1)
    print('done:', {s['role']: round(max(s['feel'][1:]), 2) for s in entry['stems'] if 'feel' in s}, file=sys.stderr)

if __name__ == '__main__': main()
