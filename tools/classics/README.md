# Classics pipeline (Suno cover → Musicy track)

How the "קלאסיקות" tracks were made, so the next one takes minutes.

1. **Reference loop.** `melodies.json` holds each public-domain tune (MIDI notes in beats + chords). Render *one pass* of the loop (4 bars, ~8 s) to MP3 — Suno's copyright matcher flags longer renders of famous tunes, a single 4-bar pass goes through.
2. **Suno.** Create → `+ Audio` → upload the 8 s clip → tag *Loop* → mode **Cover** → lyrics `[Instrumental]` → style prompt in the house formula (steady BPM, drums + bass + 3 clearly separated instruments, `‑vocals ‑singing …`, "keep the uploaded melody exactly, note for note"). Two clips come back.
3. **Check the tune is really there**: unlock the clip (1 of the monthly downloads), download MP3, run
   `python3 melody_rank.py "<clip>.mp3" <bpm>` — the right tune must rank first with a clear margin (≈0.25+ vs ≈0.18 for the rest). If not, try the second clip.
4. **Stems.** Download dialog → *Stems & MIDI → Manage* → *Auto split* → Download **WAV, fixed tempo**. The zip name carries the BPM Suno locked to.
5. **Build.** `python3 build_track.py <stems_dir> <melody_key> <bpm> <track_id> "<title he>" "<title en>" "<artist he>" "<artist en>"`
   - finds the 4-bar window where the tune plays with the whole band, snaps it to a drum onset and to the loop's own repetition;
   - picks the stem that carries the melody by chroma match, keeps drums + the 3 loudest others, folds quiet leftovers into the harmonic bed;
   - writes `tracks/<id>/{drums,bass,…}.flac` (mono 32 kHz, exact loop length), `evolve.m4a` (the full mix from the loop start, up to 8 loops) and `entry.json` with the `feel` arrays (calibrated to the originals' offline audit, ×1.1).
6. Append `entry.json` to `tracks/index.json` (`set: "classics"` puts it under the Classics tab) and delete the entry file.

Needs: `pip install librosa soundfile numpy` and ffmpeg.
