# tabscribe

An open-source take on Transcribe!: work out music by ear, with automatic tab drafts for guitar, bass and drums that you clean up by prompting Claude Code instead of editing by hand.

## How it works

The tab lives in an alphaTex file (`.atex`), a plain-text music notation format. Because it's text, Claude Code can edit it like code, and a live browser preview redraws it on every save, with playback.

```bash
tabscribe watch examples/demo.atex     # opens the live preview
```

Then, in Claude Code in this folder: *"bar 2 should be in 7th position"*, *"make the snare hits on beat 4 a flam"*, *"add a crash on the first beat"*. The file changes and the preview updates within a second. `CLAUDE.md` tells Claude Code the alphaTex conventions.

## Auto-tab pipeline (in progress)

1. **Separate** – split the mix into stems (Demucs `htdemucs_6s`: guitar, bass, drums, piano, vocals, other)
2. **Analyse** – tempo, bars, key and chords (madmom)
3. **Transcribe** – guitar and bass to notes (Basic Pitch); drums to hits (e.g. ADTOF)
4. **Fret** – assign each guitar/bass note a playable string and fret
5. **Export** – `.atex` (editable source) and `.txt` (plain-text tab, read-only)

```bash
tabscribe tab song.mp3 -o out/     # writes out/song.atex and out/song.txt
```

The output is a draft. Fixing it is what the Claude Code loop is for.

## Status

- Working: song model, alphaTex export (validated against alphaTab 1.9), plain-text tab export, live preview server, demo song.
- Stubs: the audio stages in `src/tabscribe/pipeline.py`.
- Not yet built: the practice player (slow-down, looping, EQ, note spectrum).

## Notes

- Basic Pitch is licensed CC BY-NC 4.0 (non-commercial). Fine for a hobby project; swap it out if this ever becomes a product.
- The preview loads alphaTab from the jsDelivr CDN, so it needs internet access.
- Prior art: `aguilasa/tabgen`, `bmcdonald3/AutoTab`, `JackJamesLoth/Audio2Tab`. MuScriptor (Kyutai/Mirelo) is an open multi-instrument audio-to-MIDI model worth trying for step 3.

## Dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
npm install                    # only for scripts/check_atex.mjs
python examples/make_demo.py   # regenerates examples/demo.atex and demo.txt
tabscribe watch examples/demo.atex
```
