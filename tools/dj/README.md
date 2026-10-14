# DJ tracks: from a Suno production to a Musicy track

1. Generate in Suno (Create → Advanced): instrumental, "the FIRST 8 bars are only five clearly separated parts…", then unlock the clip and
   split it (Stems & MIDI → Auto split → Download WAV, fixed tempo). The zip name carries the BPM; verify it: `python3 tempo.py <stems_dir> <bpm>`.
2. `python3 levels.py <stems_dir> <bpm> <grid_phase>` prints per-part levels per two bars when you want to pick the loop by hand (FORCE_AT=<seconds>).
3. `python3 build_dj.py <stems_dir> <bpm> <track_id> <title_he> <title_en>` writes tracks/<id>/: loop stems (drums + four parts, FLAC),
   evolve.m4a (the rest of the production, whole loops), band.json (20 Hz loudness of every part for the stage show) and entry.json.
   The loop is the first steady 4 bars where the drums groove and four parts play; leftovers are folded into the bed so the loop still sums to the mix.
   A bass whose timing cannot be heard (a sustained sub) gets `auto: true` and is placed with the drums.
4. Add entry.json to tracks/index.json (set "dj") and run tools' in-engine test (every non-anchor part should be playable).
