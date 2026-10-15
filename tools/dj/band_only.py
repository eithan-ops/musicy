#!/usr/bin/env python3
"""Recompute tracks/<id>/band.json for an existing DJ track (same maths as build_dj.py), without touching the audio.
usage: band_only.py <stems_dir> <track_id> [loop_at_seconds]   (loop_at defaults to entry.json's loop_at)"""
import sys, os, json, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dj import NAME, GUEST_COLORS, load_stereo, env_rate, b64u8, rms, db

sdir, tid = sys.argv[1:3]
odir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'tracks', tid)
entry = json.load(open(f'{odir}/entry.json'))
loop_at = float(sys.argv[3]) if len(sys.argv) > 3 else entry['loop_at']
bpm, bars, bpb = entry['bpm'], entry['bars'], entry['bpb']
SR = 32000; RATE = 40
files = sorted(f for f in os.listdir(sdir) if f.endswith('.wav'))
full = {f.split(' ', 1)[1][:-4] if ' ' in f else f[:-4]: load_stereo(os.path.join(sdir, f)) for f in files}
n48 = min(v.shape[1] for v in full.values()); full = {k: v[:, :n48] for k, v in full.items()}
L = int(round(bars * bpb * 60 / bpm * SR)); L48 = int(round(L / SR * 48000)); st48 = int(round(loop_at * 48000))
loops = entry['evolve']['bars'] // bars; T = loops * L48
tail = sum(full.values())[:, st48:st48 + T]; tail = tail * (.9 / max(1e-6, np.max(np.abs(tail))))
bar = bpb * 60 / bpm
# which source stem feeds each role: by the English name the builder gave it
by_en = {}
for k, (role, he, en, ch) in NAME.items():
    if k in full: by_en.setdefault(en, []).append(k)
name_of = {}
for s in entry['stems']:
    cands = by_en.get(s['name_en']) or by_en.get({'Oud': 'Guitar', 'Darbuka': 'Percussion'}.get(s['name_en'], ''), [])
    if s['role'] == 'drums': cands = ['Drums']
    if not cands: print('no source for', s, file=sys.stderr); continue
    name_of[s['role']] = cands[0]
print('roles:', name_of, file=sys.stderr)
envs = {}
for k, v in full.items():
    m = v[:, st48:st48 + T].mean(axis=0); e = env_rate(m, 48000, RATE)
    ref = np.percentile(e, 97) if e.max() > 1e-4 else 1
    loopref = np.percentile(e[:int(L / SR * RATE)], 90)
    if loopref > ref * .03: ref = min(ref, loopref / .6)
    envs[k] = np.clip(e / (ref + 1e-9), 0, 1)
mixm = tail.mean(axis=0); energy = env_rate(mixm, 48000, RATE); energy = np.clip(energy / (np.percentile(energy, 97) + 1e-9), 0, 1)
bar_frames = int(round(bar * RATE)); nbar = len(energy) // bar_frames
be = np.array([energy[i * bar_frames:(i + 1) * bar_frames].mean() for i in range(nbar)])
drops = []; last = -99
for i in range(1, nbar):
    prev = be[max(0, i - 4):i].mean()
    if be[i] - prev > .18 and be[i] > .58 and i - last >= 16: drops.append(round(i * bar, 2)); last = i
core = {role: b64u8(envs[src]) for role, src in name_of.items() if src in envs}
guests = []
for k in envs:
    if k in name_of.values(): continue
    if db(rms(full[k][:, st48:st48 + T].mean(axis=0)), rms(mixm)) < -26: continue
    role, he, en, ch = NAME.get(k, ('counter', k, k, 'synth'))
    guests.append({'name': he, 'name_en': en, 'char': ch, 'color': GUEST_COLORS[len(guests) % len(GUEST_COLORS)], 'env': b64u8(envs[k])})
band = {'rate': RATE, 'n': len(energy), 'core': core, 'guests': guests, 'energy': b64u8(energy), 'drops': drops}
json.dump(band, open(f'{odir}/band.json', 'w'), ensure_ascii=False, separators=(',', ':'))
entry['loop_at'] = loop_at; json.dump(entry, open(f'{odir}/entry.json', 'w'), ensure_ascii=False, indent=1)
print(tid, 'band: core', list(core), 'guests', [g['name_en'] for g in guests], 'drops', drops, '(%.0fs)' % (T / 48000))
