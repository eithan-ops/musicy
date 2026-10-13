#!/usr/bin/env python3
"""Turn a Suno stems folder into a Musicy track folder (loop stems as FLAC + evolve.m4a) and print the index.json entry.
usage: build_track.py <stems_dir> <melody_key> <bpm> <track_id> <title_he> <title_en> <artist_he> <artist_en> [bars]
"""
import sys, os, json, subprocess, numpy as np, librosa
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from melody_check import template
from feel import feel_arrays, load_mono

SR = 32000
M = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'melodies.json')))
NAME = {  # Suno stem name -> (role, he, en)
  'Drums': ('drums', 'תופים', 'Drums'), 'Percussion': ('perc', 'כלי הקשה', 'Percussion'), 'Bass': ('bass', 'בס', 'Bass'),
  'Keyboard': ('chords', 'פסנתר', 'Piano'), 'Guitar': ('arp', 'גיטרה', 'Guitar'), 'Synth': ('melody', 'סינת׳', 'Synth'),
  'Strings': ('counter', 'כלי מיתר', 'Strings'), 'Brass': ('counter', 'כלי נשיפה', 'Brass'), 'Other': ('counter', 'ליווי', 'Backing'),
  'Lead Vocal': ('melody', 'קול', 'Voice'), 'Backing Vocals': ('counter', 'קולות רקע', 'Backing vocals'), 'Woodwinds': ('counter', 'חליל', 'Flute'),
}
ROLE_SLOTS = ['bass', 'chords', 'arp', 'counter', 'perc', 'melody']

def rms(y): return float(np.sqrt(np.mean(y * y) + 1e-12))

def main():
    sdir, key, bpm, tid, title_he, title_en, artist_he, artist_en = sys.argv[1:9]
    bpm = float(bpm); d = M[key]; bpb = d['bpb']; bars = int(sys.argv[9]) if len(sys.argv) > 9 else d['bars']
    files = sorted(f for f in os.listdir(sdir) if f.endswith('.wav'))
    stems = {}
    for f in files:
        name = f.split(' ', 1)[1][:-4]
        stems[name] = load_mono(os.path.join(sdir, f), SR)
    n = min(len(v) for v in stems.values())
    for k in stems: stems[k] = stems[k][:n]
    mix = sum(stems.values())
    peak = np.max(np.abs(mix)); loud = {k: rms(v) for k, v in stems.items()}
    top = max(loud.values())
    print('stems:', {k: round(20 * np.log10(v / top), 1) for k, v in loud.items()}, file=sys.stderr)

    # --- where does the hook play, with the whole band? chroma match at the known tempo, then snap to a drum onset
    hop = 256; chroma = librosa.feature.chroma_stft(y=mix, sr=SR, n_fft=2048, hop_length=hop, norm=1); fps = SR / hop
    tmpl, tot = template(d['mel']); bs = 60 / bpm; L = int(round(bars * bpb * bs * SR)); Lf = int(round(tot * bs * fps))
    idx = np.full(Lf, -1, dtype=int)
    for t0, dur, p in tmpl:
        a, b = int(round(t0 * bs * fps)), int(round((t0 + dur) * bs * fps)); idx[a:b] = p
    valid = idx >= 0; F = chroma.shape[1]
    best = []
    for tr in range(12):
        pcs = (idx + tr) % 12
        for off in range(0, F - Lf, 2):
            seg = chroma[:, off:off + Lf]; s = seg[pcs[valid], np.arange(Lf)[valid]].mean()
            best.append((s, off, tr))
    best.sort(reverse=True)
    # candidates: distinct starts (>= 1 bar apart), keep the strongest 12
    cands = []
    for s, off, tr in best:
        if all(abs(off - o) > fps * bpb * bs for _, o, _ in cands): cands.append((s, off, tr))
        if len(cands) >= 12: break
    others = sorted([k for k in stems if k not in ('Drums', 'Percussion')], key=lambda k: -loud[k])
    main = (['Drums'] if 'Drums' in stems else []) + [k for k in others if loud[k] > top * 10 ** (-12 / 20)][:4]
    drums = stems.get('Drums', mix)
    oenv = librosa.onset.onset_strength(y=drums, sr=SR, hop_length=hop)
    def snap(off):
        lo, hi = max(0, off - int(fps * .15)), min(len(oenv) - 1, off + int(fps * .15)); j = lo + int(np.argmax(oenv[lo:hi + 1])); return j
    scored = []
    for s, off, tr in cands:
        st = int(snap(off) * hop)
        if st + L > n: continue
        # the whole band should be playing: every kept stem at least -18 dB of its own song-wide loudness
        cover = min(rms(stems[k][st:st + L]) / (loud[k] + 1e-9) for k in main)
        # prefer a spot where the band is full: count the non-drum stems that are clearly audible in this window
        lv = {k: rms(stems[k][st:st + L]) for k in stems if k not in ('Drums', 'Percussion')}; lt = max(lv.values()) + 1e-9
        nz = sum(1 for v in lv.values() if v > lt * 10 ** (-16 / 20))
        scored.append((s * min(1, cover / .6) * (.55 + .15 * min(3, nz)), s, cover, st, tr, nz))
    scored.sort(reverse=True)
    for x in scored[:5]: print('cand score %.3f mel %.3f cover %.2f at %.2fs tr %d stems %d' % (x[0], x[1], x[2], x[3] / SR, x[4], x[5]), file=sys.stderr)
    _, mscore, cover, st, tr, _ = scored[0]

    # --- refine the start: the loop should repeat itself, so slide ±60 ms for the best self-similarity at L
    win = np.ones(int(SR * .004)) / int(SR * .004); env = np.convolve(np.abs(drums), win, mode='same'); env = np.diff(env, prepend=0); env[env < 0] = 0
    bestc, bestd = -1, 0
    for dlt in range(-int(SR * .06), int(SR * .06), 16):
        a, b = st + dlt, st + dlt + L
        if a < 0 or b + L > n: continue
        x, y2 = env[a:b], env[b:b + L]
        c = float(np.dot(x, y2) / (np.linalg.norm(x) * np.linalg.norm(y2) + 1e-9))
        if c > bestc: bestc, bestd = c, dlt
    st += bestd; print('loop start %.3fs, self-similarity %.3f, L %.3fs' % (st / SR, bestc, L / SR), file=sys.stderr)

    # --- roles: melody = the stem that carries the tune in the loop; drums absorb percussion; keep drums + 4
    cut = {k: v[st:st + L].copy() for k, v in stems.items()}
    def melscore(y):
        ch = librosa.feature.chroma_stft(y=y, sr=SR, n_fft=2048, hop_length=hop, norm=1); Fz = ch.shape[1]
        pcs = (idx + tr) % 12; m = min(Lf, Fz); return float(ch[pcs[:m][valid[:m]], np.arange(m)[valid[:m]]].mean())
    lo = {k: rms(v) for k, v in cut.items()}; ltop = max(lo.values())
    melodic = {k: melscore(v) for k, v in cut.items() if k not in ('Drums', 'Percussion') and lo[k] > ltop * .08}
    print('melody scores:', {k: round(v, 3) for k, v in melodic.items()}, file=sys.stderr)
    mel_stem = max(melodic, key=melodic.get)
    out = {}
    drum = cut.get('Drums', np.zeros(L, np.float32)).copy()
    if 'Percussion' in cut and lo['Percussion'] < ltop * .35: drum += cut['Percussion']; cut.pop('Percussion')
    out['drums'] = ('drums', 'תופים', 'Drums', drum)
    rest = [k for k in cut if k not in ('Drums',)]
    rest.sort(key=lambda k: -lo[k])
    chosen = [mel_stem] + [k for k in rest if k != mel_stem and lo[k] > ltop * 10 ** (-16 / 20)][:3]
    leftovers = [k for k in rest if k not in chosen]
    used = set(['drums'])
    for k in chosen:
        role, he, en = NAME.get(k, ('counter', k, k))
        if k == mel_stem: role = 'melody'
        elif role == 'melody': role = 'counter'
        if role in used: role = next(r for r in ['counter', 'arp', 'perc', 'chords', 'bass'] if r not in used)
        used.add(role); out[role] = (role, he, en, cut[k].copy())
    # quiet leftovers go into the harmonic bed so the loop still sums to the full mix
    bed = next((r for r in ['chords', 'arp', 'counter', 'perc', 'bass'] if r in out), 'melody')
    for k in leftovers: out[bed][3][:] += cut[k]; print('folded', k, 'into', bed, file=sys.stderr)

    # --- export: FLAC mono 32k with 3 ms edge fades; evolve = full stereo mix from the loop start
    odir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tracks', tid); os.makedirs(odir, exist_ok=True)
    for f in os.listdir(odir): os.remove(os.path.join(odir, f))
    fade = int(SR * .003); ramp = np.linspace(0, 1, fade, dtype=np.float32)
    g = .9 / peak
    entry_stems = []
    arrs = {}
    for role, (r, he, en, y) in out.items():
        y = y * g; y[:fade] *= ramp; y[-fade:] *= ramp[::-1]; arrs[role] = y
        raw = (np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', '-c:a', 'flac', f'{odir}/{role}.flac'], input=raw, check=True)
        entry_stems.append({'role': role, 'file': f'{role}.flac', 'name': he, 'name_en': en})
    U = bars * bpb * 4
    feel = feel_arrays(arrs, SR, bpm, U)
    for s in entry_stems:
        if s['role'] in feel: s['feel'] = [round(v * 1.1, 2) for v in feel[s['role']]]
    # evolve: stereo from original wavs, from loop start, whole loops only, trimmed of trailing silence
    full = sum(load_stereo(os.path.join(sdir, f)) for f in files)
    st48 = int(round(st / SR * 48000)); tail = full[:, st48:]
    env = np.abs(tail).max(axis=0) if tail.ndim == 2 else np.abs(tail)
    nz = np.where(env > 1e-3)[0]; end = nz[-1] if len(nz) else len(env)
    L48 = int(round(L / SR * 48000)); loops = min(8, max(1, int(end / L48 + .02))); tail = tail[:, :loops * L48] if tail.ndim == 2 else tail[:loops * L48]
    tail = tail * (.9 / max(1e-6, np.max(np.abs(tail))))
    raw = (np.clip(tail.T if tail.ndim == 2 else tail, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 's16le', '-ar', '48000', '-ac', '2' if tail.ndim == 2 else '1', '-i', '-', '-ar', '44100', '-c:a', 'aac', '-b:a', '128k', f'{odir}/evolve.m4a'], input=raw, check=True)
    order = {'drums': -1, 'bass': 0, 'chords': 1, 'arp': 2, 'perc': 3, 'counter': 4, 'melody': 5}
    entry_stems.sort(key=lambda s: order[s['role']])
    entry = {'id': tid, 'title': title_he, 'title_en': title_en, 'artist': artist_he, 'artist_en': artist_en, 'bpm': round(bpm, 2), 'bpb': bpb, 'bars': bars,
             'stems': entry_stems, 'active': True, 'source': 'suno', 'set': 'classics', 'melody': key, 'evolve': {'file': 'evolve.m4a', 'bars': loops * bars}}
    json.dump(entry, open(f'{odir}/entry.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: (v if k != 'stems' else [(s['role'], s['name_en'], round(max(s['feel'][1:]), 2) if 'feel' in s else None) for s in v]) for k, v in entry.items()}, ensure_ascii=False))

def load_stereo(path, sr=48000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(sr), '-'], capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32); return a.reshape(-1, 2).T.copy()

if __name__ == '__main__': main()
