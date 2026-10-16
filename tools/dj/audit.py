#!/usr/bin/env python3
"""Audit every playable stem in the catalog: can a human HEAR whether it is in time?
   feel (log-mel change when shifted) says a shift changes the spectrogram; it does not say the change sounds like a rhythm.
   A noise sweep, a sidechained pad or a soft shaker all score well on feel and still "sound like noise" in the game.
   This prints, per stem:
     level   dB below the loudest stem in the loop (quiet parts hide behind the band)
     flat    spectral flatness 0..1 (noise-like > .25)
     pulse   how periodic the onsets are at the beat grid (0..1, clear groove > .35)
     crest   onset peak / mean (transient attacks > 4; a pad ~ 1-2)
     sustain fraction of the loop the envelope stays above half its peak (pad ~ .8+, plucks < .35)
     hear    a single 0..10 "audible timing" score; < 4 = the player will struggle
usage: audit.py [set] (default: dj)  — add -v to list every shift"""
import sys, os, json, numpy as np, librosa, subprocess
HERE = os.path.dirname(os.path.abspath(__file__)); ROOT = os.path.join(HERE, '..', '..')
SR = 32000; HOP = 256

def load(path):
    raw = subprocess.run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'f32le', '-ac', '1', '-ar', str(SR), '-'], capture_output=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()

def stats(y, bpm, bpb, bars):
    rms = float(np.sqrt(np.mean(y * y) + 1e-12))
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=HOP)) ** 2
    flat = float(np.mean(librosa.feature.spectral_flatness(S=S)))
    cent = float(np.mean(librosa.feature.spectral_centroid(S=S, sr=SR)))
    on = librosa.onset.onset_strength(S=librosa.power_to_db(librosa.feature.melspectrogram(S=S, sr=SR, n_mels=64)), sr=SR, hop_length=HOP)
    on = on - on.mean(); fps = SR / HOP; beat = 60 / bpm * fps
    e = float(np.dot(on, on)) + 1e-9
    def ac(lag):
        lag = int(round(lag)); return float(np.dot(on, np.roll(on, lag)) / e)
    pulse = max(ac(beat), ac(beat / 2), ac(beat * 2))      # groove repeats at the beat or half-beat
    anti = ac(beat / 2 * .5 + beat / 4)                      # an off-grid lag: a clear rhythm is LOW here
    raw = librosa.onset.onset_strength(y=y, sr=SR, hop_length=HOP)
    crest = float(raw.max() / (raw.mean() + 1e-9))
    env = librosa.feature.rms(y=y, frame_length=1024, hop_length=HOP)[0]
    sustain = float(np.mean(env > env.max() * .5))
    return dict(rms=rms, flat=flat, cent=cent, pulse=pulse, anti=anti, crest=crest, sustain=sustain)

def hear_score(s, level_db):
    """0..10: how audibly the stem's timing reads to a listener in the mix."""
    sc = 10.0
    sc -= max(0, -level_db - 6) * .35          # buried: -6 dB fine, -14 dB costs ~3
    sc -= max(0, s['flat'] - .12) * 25          # noise-like
    sc -= max(0, .45 - s['pulse']) * 8          # no groove periodicity
    sc -= max(0, s['sustain'] - .55) * 7        # pad: always on, no attacks to place
    sc -= max(0, 4 - s['crest']) * .6           # soft attacks
    return max(0, min(10, sc))

def main():
    want = [a for a in sys.argv[1:] if not a.startswith('-')]; want = want[0] if want else 'dj'
    idx = json.load(open(os.path.join(ROOT, 'tracks', 'index.json')))
    rows = []
    for t in idx['tracks']:
        if want != 'all' and (t.get('set') or 'hits') != want: continue
        if want == 'all' and not t.get('active', True): continue
        base = os.path.join(ROOT, 'tracks', t['id'])
        ys = {s['role']: load(os.path.join(base, s['file'])) for s in t['stems']}
        n = min(len(v) for v in ys.values()); ys = {k: v[:n] for k, v in ys.items()}
        top = max(np.sqrt(np.mean(v * v)) for v in ys.values())
        print('\n%s  %s  %g bpm' % (t['id'], t.get('title_en', ''), t['bpm']))
        print('  %-9s %-14s %6s %5s %5s %5s %6s %5s %5s' % ('role', 'name', 'level', 'flat', 'pulse', 'crest', 'sust', 'feel', 'HEAR'))
        for s in t['stems']:
            if s['role'] == 'drums' or s.get('auto'): continue
            st = stats(ys[s['role']], t['bpm'], t['bpb'], t['bars'])
            lv = 20 * np.log10(st['rms'] / top + 1e-9)
            h = hear_score(st, lv); fm = max(s['feel'][1:]) if s.get('feel') else 0
            flag = '  <-- noise' if st['flat'] > .2 else ('  <-- pad' if st['sustain'] > .6 else ('  <-- buried' if lv < -14 else ''))
            if h >= 6: flag = ''
            print('  %-9s %-14s %6.1f %5.2f %5.2f %5.1f %6.2f %5.2f %5.1f%s' % (s['role'], s.get('name_en', ''), lv, st['flat'], st['pulse'], st['crest'], st['sustain'], fm, h, flag))
            rows.append((t['id'], s['role'], s.get('name_en', ''), round(lv, 1), round(st['flat'], 2), round(st['pulse'], 2), round(st['crest'], 1), round(st['sustain'], 2), fm, round(h, 1)))
    json.dump([[float(x) if isinstance(x,(np.floating,)) else x for x in r] for r in rows], open(os.path.join(HERE, 'audit_%s.json' % want), 'w'))

if __name__ == '__main__': main()
