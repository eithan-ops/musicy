#!/usr/bin/env python3
"""Turn a Suno stems folder of an ORIGINAL Musicy DJ track into a game track:
   loop stems (FLAC) = the first steady 4 bars where the five core parts all play,
   evolve.m4a = the rest of the production from the loop start (whole loops),
   band.json = low-rate loudness envelopes of every part over the evolve section (core + guests), energy and drops,
   so the stage can show the whole band playing while the full track runs.
usage: build_dj.py <stems_dir> <bpm> <track_id> <title_he> <title_en> [bars=4] [bpb=4]
env: FORCE_AT=<seconds> to hand-pick the loop start (snapped to the bar grid), MAX_LOOPS (default 40)
"""
import sys, os, json, base64, subprocess, numpy as np, librosa
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'classics'))
from feel import feel_arrays, load_mono

SR = 32000; HOP = 256
NAME = {  # Suno stem name -> (role, he, en, character)
  'Drums': ('drums', 'תופים', 'Drums', 'drums'), 'Percussion': ('perc', 'כלי הקשה', 'Percussion', 'perc'), 'Bass': ('bass', 'בס', 'Bass', 'bass'),
  'Keyboard': ('chords', 'קלידים', 'Keys', 'keys'), 'Piano': ('chords', 'פסנתר', 'Piano', 'keys'), 'Guitar': ('arp', 'גיטרה', 'Guitar', 'guitar'),
  'Synth': ('melody', 'סינת׳', 'Synth', 'synth'), 'Strings': ('counter', 'כינורות', 'Strings', 'violin'), 'Brass': ('counter', 'חצוצרות', 'Brass', 'trumpet'),
  'Woodwinds': ('counter', 'סקסופון', 'Sax', 'sax'), 'Lead Vocal': ('melody', 'ווקאל', 'Vocal', 'synth'), 'Lead Vocals': ('melody', 'ווקאל', 'Vocal', 'synth'), 'Backing Vocals': ('counter', 'קולות רקע', 'Backing vocals', 'synth'),
  'Other': ('counter', 'אפקטים', 'FX', 'synth'), 'FX': ('perc', 'אפקטים', 'FX', 'synth'),
}
COLORS = {'drums': '#FF5A4E', 'bass': '#22C1F0', 'chords': '#FF9F1C', 'arp': '#B48CFF', 'perc': '#14C9A8', 'counter': '#FF5DC8', 'melody': '#2BD67B'}
GUEST_COLORS = ['#FFD23F', '#FF7A59', '#7CF2C4', '#C9A0FF', '#FF9DE2', '#8FE3FF']

def rms(y): return float(np.sqrt(np.mean(y * y) + 1e-12))
def db(a, b): return 20 * np.log10((a + 1e-9) / (b + 1e-9))

def load_stereo(path, sr=48000):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '2', '-ar', str(sr), '-'], capture_output=True).stdout
    a = np.frombuffer(raw, dtype=np.float32); return a.reshape(-1, 2).T.copy()

def env_rate(y, sr, rate):
    hop = int(round(sr / rate)); n = len(y) // hop
    e = np.sqrt(np.mean(y[:n * hop].reshape(n, hop) ** 2, axis=1) + 1e-12); return e

def b64u8(v):
    return base64.b64encode(np.clip(np.round(v * 100), 0, 100).astype(np.uint8).tobytes()).decode()

def main():
    sdir, bpm, tid, title_he, title_en = sys.argv[1:6]
    bpm = float(bpm); bars = int(sys.argv[6]) if len(sys.argv) > 6 else 4; bpb = int(sys.argv[7]) if len(sys.argv) > 7 else 4
    files = sorted(f for f in os.listdir(sdir) if f.endswith('.wav'))
    stems = {}
    for f in files:
        name = f.split(' ', 1)[1][:-4] if ' ' in f else f[:-4]
        stems[name] = load_mono(os.path.join(sdir, f), SR)
    n = min(len(v) for v in stems.values())
    for k in stems: stems[k] = stems[k][:n]
    mix = sum(stems.values()); peak = float(np.max(np.abs(mix)))
    loud = {k: rms(v) for k, v in stems.items()}; top = max(loud.values())
    print('stems:', {k: round(db(v, top), 1) for k, v in loud.items()}, file=sys.stderr)
    bs = 60 / bpm; L = int(round(bars * bpb * bs * SR)); bar = bpb * bs

    # --- bar grid: the phase (within one bar) where drum onsets line up with the beats, downbeat weighted
    drums = stems.get('Drums', mix)
    oenv = librosa.onset.onset_strength(y=drums, sr=SR, hop_length=HOP); fps = SR / HOP
    beat_f = bs * fps; bar_f = bar * fps; nb = int((len(oenv) - 1) // beat_f)
    best_ph, best_s = 0, -1
    for ph in np.arange(0, bar_f, 1.0):
        s = 0.0
        for k in range(nb):
            t = ph + k * beat_f
            if t >= len(oenv) - 1: break
            w = 2.0 if (k % bpb) == 0 else 1.0; s += w * oenv[int(round(t))]
        if s > best_s: best_s, best_ph = s, ph
    grid = [best_ph + k * bar_f for k in range(int((len(oenv) - best_ph) / bar_f))]
    # the song may start on a silent half-bar: bars start where drum energy first shows up
    print('grid phase %.3fs, %d bars' % (best_ph / fps, len(grid)), file=sys.stderr)

    # --- candidate loops: each bar start; the window's own loudest part is the reference (an intro is quieter than a drop):
    #     a part "plays" if it is within 12 dB of it and steady across both halves; the loop wants drums + bass + 3 more,
    #     with as little left over as possible (leftovers get folded into the bed), as early as possible (the intro IS the five parts)
    def window_stats(st):
        seg = {k: v[st:st + L] for k, v in stems.items()}
        lv = {k: rms(v) for k, v in seg.items()}; ref = max([v for k, v in lv.items() if k != 'Drums'] or [1e-9]) + 1e-9
        on = [k for k in stems if k != 'Drums' and db(lv[k], ref) > -12 and db(lv[k], top) > -30]
        steady = [k for k in on if db(rms(seg[k][:L // 2]), lv[k]) > -6 and db(rms(seg[k][L // 2:]), lv[k]) > -6]
        drums_ok = 'Drums' in stems and db(lv['Drums'], ref) > -18 and db(rms(seg['Drums'][:L // 2]), lv['Drums']) > -6 and db(rms(seg['Drums'][L // 2:]), lv['Drums']) > -6
        pool = sorted([k for k in steady if k != 'Drums'], key=lambda k: -lv[k])
        pick = (['Bass'] if 'Bass' in pool else []) + [k for k in pool if k != 'Bass']
        pick = pick[:4]
        left = [k for k in stems if k not in pick and k != 'Drums']
        ratio = sum(lv[k] ** 2 for k in left) / (sum(lv[k] ** 2 for k in stems) + 1e-12)
        return lv, pick, drums_ok, ratio
    cands = []
    for bi, gf in enumerate(grid):
        st = int(gf * HOP)
        if st + L > n: break
        if st / SR < 0.05: continue
        lv, pick, drums_ok, ratio = window_stats(st)
        a, b = oenv[int(gf):int(gf + bar_f * (bars // 2))], oenv[int(gf + bar_f * (bars // 2)):int(gf + bar_f * bars)]
        m = min(len(a), len(b)); c = float(np.dot(a[:m], b[:m]) / (np.linalg.norm(a[:m]) * np.linalg.norm(b[:m]) + 1e-9)) if m else 0
        drums_ok = drums_ok and c >= .5  # a groove repeats bar to bar; fills and risers do not
        score = (2.0 if drums_ok else 0) + len(pick) * 1.0 + c * .5 - ratio * 3 - bi * 0.05
        cands.append((score, bi, st, len(pick), c, drums_ok, ratio, pick))
    cands.sort(reverse=True)
    for x in cands[:6]: print('cand %.2f bar %d at %.2fs parts %d steady %.2f drums %s left %.2f %s' % (x[0], x[1], x[2] / SR, x[3], x[4], x[5], x[6], x[7]), file=sys.stderr)
    # the game's own test decides between the close candidates: how many parts are "playable" (shifting them is clearly audible)
    def playable(st, pick):
        cutw = {k: v[st:v.size and st + L] for k, v in stems.items() if k in pick or k == 'Drums'}
        fa = feel_arrays({('drums' if k == 'Drums' else k): v for k, v in cutw.items()}, SR, bpm, bars * bpb * 4)
        return sum(1 for k, a in fa.items() if max(a[1:]) * 1.1 >= 1.5), {k: round(max(a[1:]) * 1.1, 2) for k, a in fa.items()}
    close = [x for x in cands[:5] if x[0] >= cands[0][0] - .6]
    ranked = []
    for x in close:
        npl, fm = playable(x[2], x[7]); ranked.append((npl, x[0], x, fm)); print('  bar %d playable %d %s' % (x[1], npl, fm), file=sys.stderr)
    ranked.sort(key=lambda r: (-r[0], -r[1]))
    _, bi, st, _, c, _, _, pick = ranked[0][2]
    if os.environ.get('FORCE_AT'):
        want = float(os.environ['FORCE_AT']) * SR; st = int(min(grid, key=lambda g: abs(g * HOP - want)) * HOP)
        _, pick, _, _ = window_stats(st); print('forced start %.2fs' % (st / SR), file=sys.stderr)
    # snap to the nearest drum onset (±40 ms), then slide ±30 ms so bar 1 best matches bar 2 (a clean loop seam)
    f0 = st / HOP; lo, hi = max(0, int(f0 - fps * .04)), min(len(oenv) - 1, int(f0 + fps * .04)); st = int((lo + int(np.argmax(oenv[lo:hi + 1]))) * HOP)
    win = int(SR * .004); e = np.convolve(np.abs(drums), np.ones(win) / win, mode='same'); e = np.diff(e, prepend=0); e[e < 0] = 0
    Lb = int(round(bar * SR)); bestc, bestd = -1, 0
    for dlt in range(-int(SR * .03), int(SR * .03), 16):
        a, b = st + dlt, st + dlt + Lb
        if a < 0 or b + Lb > n: continue
        x, y2 = e[a:b], e[b:b + Lb]; cc = float(np.dot(x, y2) / (np.linalg.norm(x) * np.linalg.norm(y2) + 1e-9))
        if cc > bestc: bestc, bestd = cc, dlt
    st += bestd; print('loop start %.3fs (bar %d), seam %.3f, L %.3fs' % (st / SR, bi, bestc, L / SR), file=sys.stderr)

    # --- roles: drums + the four loudest steady parts; the rest are folded into the bed so the loop sums to the mix
    cut = {k: v[st:st + L].copy() for k, v in stems.items()}
    lo = {k: rms(v) for k, v in cut.items()}; ltop = max(lo.values())
    drum = cut.get('Drums', np.zeros(L, np.float32)).copy()
    pool = [k for k in cut if k != 'Drums']; pool.sort(key=lambda k: -lo[k])
    chosen = list(pick) if len(pick) >= 3 else pool[:4]
    out = {'drums': ('drums', 'תופים', 'Drums', drum)}; used = {'drums'}
    # the lead: a synth / vocal if present, else the brightest tonal part
    def centroid(y): return float(np.mean(librosa.feature.spectral_centroid(y=y, sr=SR)))
    roles = {}
    for k in chosen: roles[k] = NAME.get(k, ('counter', k, k, 'synth'))[0]
    if 'melody' not in roles.values():
        cand = [k for k in chosen if roles[k] not in ('bass', 'perc')]
        if cand: roles[max(cand, key=lambda k: centroid(cut[k]))] = 'melody'
    name_of = {'drums': 'Drums'}
    for k in chosen:
        role, he, en, ch = NAME.get(k, ('counter', k, k, 'synth')); role = roles[k]
        if role in used: role = next(r for r in ['counter', 'arp', 'chords', 'perc', 'bass', 'melody'] if r not in used)
        used.add(role); out[role] = (role, he, en, cut[k].copy()); name_of[role] = k
    # leftovers are folded where they belong musically, so the loop still sums to the real mix: percussion into the drums,
    # vocal chops into the lead, everything else into the harmonic bed
    leftovers = [k for k in pool if k not in chosen]
    bed = next((r for r in ['chords', 'arp', 'counter', 'perc', 'bass'] if r in out), 'melody')
    for k in leftovers:
        if lo[k] <= 1e-5: continue
        dest = 'drums' if k in ('Percussion',) else ('melody' if k in ('Lead Vocal', 'Lead Vocals', 'Backing Vocals') and 'melody' in out and name_of['melody'] not in ('Lead Vocal', 'Lead Vocals') else bed)
        out[dest][3][:] += cut[k]; print('folded', k, 'into', dest, '(%.1f dB)' % db(lo[k], ltop), file=sys.stderr)
    print('roles:', {r: v[2] for r, v in out.items()}, file=sys.stderr)

    # --- export loop stems
    odir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tracks', tid); os.makedirs(odir, exist_ok=True)
    for f in os.listdir(odir): os.remove(os.path.join(odir, f))
    fade = int(SR * .003); ramp = np.linspace(0, 1, fade, dtype=np.float32); g = .9 / peak
    entry_stems, arrs = [], {}
    for role, (r, he, en, y) in out.items():
        y = y * g; y[:fade] *= ramp; y[-fade:] *= ramp[::-1]; arrs[role] = y
        raw = (np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes()
        subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 's16le', '-ar', str(SR), '-ac', '1', '-i', '-', '-c:a', 'flac', f'{odir}/{role}.flac'], input=raw, check=True)
        entry_stems.append({'role': role, 'file': f'{role}.flac', 'name': he, 'name_en': en})
    U = bars * bpb * 4
    feel = feel_arrays(arrs, SR, bpm, U)
    for s in entry_stems:
        if s['role'] in feel: s['feel'] = [round(v * 1.1, 2) for v in feel[s['role']]]
        # a part whose timing cannot be heard (a sustained sub bass) joins the drums as the groove the player builds on
        if s['role'] == 'bass' and 'feel' in s and max(s['feel'][1:]) < 1.5: s['auto'] = True; print('bass is auto (feel %.2f)' % max(s['feel'][1:]), file=sys.stderr)

    # --- evolve: the whole production from the loop start, whole loops, trailing silence trimmed
    full = {f.split(' ', 1)[1][:-4] if ' ' in f else f[:-4]: load_stereo(os.path.join(sdir, f)) for f in files}
    n48 = min(v.shape[1] for v in full.values()); full = {k: v[:, :n48] for k, v in full.items()}
    st48 = int(round(st / SR * 48000)); L48 = int(round(L / SR * 48000))
    tail = sum(full.values())[:, st48:]
    envt = np.abs(tail).max(axis=0); nzi = np.where(envt > 2e-3)[0]; end = nzi[-1] if len(nzi) else len(envt)
    loops = min(int(os.environ.get('MAX_LOOPS', 40)), max(1, int(end / L48 + .02))); tail = tail[:, :loops * L48]
    tail = tail * (.9 / max(1e-6, np.max(np.abs(tail))))
    raw = (np.clip(tail.T, -1, 1) * 32767).astype(np.int16).tobytes()
    subprocess.run(['ffmpeg', '-y', '-v', 'error', '-f', 's16le', '-ar', '48000', '-ac', '2', '-i', '-', '-ar', '44100', '-c:a', 'aac', '-b:a', '128k', f'{odir}/evolve.m4a'], input=raw, check=True)

    # --- band.json: 20 Hz loudness of every part over the evolve section (core by role, the rest as guests)
    RATE = 40; T = loops * L48
    envs = {}
    for k, v in full.items():
        m = v[:, st48:st48 + T].mean(axis=0); e = env_rate(m, 48000, RATE)
        ref = np.percentile(e, 97) if e.max() > 1e-4 else 1
        # a part that already plays in the loop should look alive from the first bar, even if the drop is much louder later
        loopref = np.percentile(e[:int(L / SR * RATE)], 90)
        if loopref > ref * .03: ref = min(ref, loopref / .6)
        envs[k] = np.clip(e / (ref + 1e-9), 0, 1)
    mixm = tail.mean(axis=0); energy = env_rate(mixm, 48000, RATE); energy = np.clip(energy / (np.percentile(energy, 97) + 1e-9), 0, 1)
    # drops: a bar where the smoothed energy jumps by 35% over the bar before, after at least 4 bars since the last one
    bar_frames = int(round(bar * RATE)); nbar = len(energy) // bar_frames
    be = np.array([energy[i * bar_frames:(i + 1) * bar_frames].mean() for i in range(nbar)])
    drops = []; last = -99
    print('bar energy:', ' '.join('%.2f' % v for v in be), file=sys.stderr)
    for i in range(1, nbar):
        prev = be[max(0, i - 4):i].mean()
        if be[i] - prev > .18 and be[i] > .58 and i - last >= 16: drops.append(round(i * bar, 2)); last = i
    core = {}
    for role, src in name_of.items():
        if src in envs: core[role] = b64u8(envs[src])
    guests = []
    for k in envs:
        if k in name_of.values(): continue
        e = envs[k]
        if db(rms(full[k][:, st48:st48 + T].mean(axis=0)), rms(mixm)) < -26: continue  # never really audible
        role, he, en, ch = NAME.get(k, ('counter', k, k, 'synth'))
        guests.append({'name': he, 'name_en': en, 'char': ch, 'color': GUEST_COLORS[len(guests) % len(GUEST_COLORS)], 'env': b64u8(e)})
    band = {'rate': RATE, 'n': len(energy), 'core': core, 'guests': guests, 'energy': b64u8(energy), 'drops': drops}
    json.dump(band, open(f'{odir}/band.json', 'w'), ensure_ascii=False, separators=(',', ':'))
    print('band: core %s guests %s drops %s (%.0fs)' % (list(core), [g['name_en'] for g in guests], drops, T / 48000), file=sys.stderr)

    order = {'drums': -1, 'bass': 0, 'chords': 1, 'arp': 2, 'perc': 3, 'counter': 4, 'melody': 5}
    entry_stems.sort(key=lambda s: order[s['role']])
    entry = {'id': tid, 'title': title_he, 'title_en': title_en, 'artist': 'Musicy DJ', 'artist_en': 'Musicy DJ', 'bpm': round(bpm, 2), 'bpb': bpb, 'bars': bars,
             'stems': entry_stems, 'active': True, 'source': 'suno', 'set': 'dj', 'evolve': {'file': 'evolve.m4a', 'bars': loops * bars, 'band': 'band.json'}, 'loop_at': round(st / SR, 3)}
    json.dump(entry, open(f'{odir}/entry.json', 'w'), ensure_ascii=False, indent=1)
    print(json.dumps({k: (v if k != 'stems' else [(s['role'], s['name_en'], round(max(s['feel'][1:]), 2) if 'feel' in s else None) for s in v]) for k, v in entry.items()}, ensure_ascii=False))

if __name__ == '__main__': main()
