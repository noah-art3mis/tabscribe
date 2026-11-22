# tabscribe

Turn a recording into tabs for guitar, bass and drums, view them Guitar Pro-style in the browser, and clean them up by prompting Claude Code instead of editing by hand.

## How it works

1. **Transcribe.** A pipeline of models separates the instruments, finds the beat, bars and chords, hears the notes and drum hits, snaps them to the grid and picks strings and frets. The result is an `.atex` file (alphaTex, a plain-text music notation format).
2. **Look and listen.** `tabscribe web songs/` opens a local app: score with tab and optional notation, playback with a cursor, per-track mute, solo and volume, speed, loop and metronome.
3. **Fix by prompting.** In Claude Code, in this folder: *"bar 2 should be in 7th position"*, *"those are hammer-ons"*, *"add a crash on the first beat"*. It edits the `.atex` file and the app redraws within a second. `CLAUDE.md` gives Claude Code the rules. You can also edit the source in the app's side panel.

## Setup

```bash
python3.11 -m venv .venv && source .venv/bin/activate
pip install -e ".[ml,dev]"     # models: Basic Pitch, madmom, ADTOF, Demucs (needs PyTorch)
npm install                     # alphaTab, used by the app and to read/validate .atex
```

## Use

```bash
tabscribe web songs/            # the app; "Transcribe audio…" turns a recording into a song
tabscribe tab song.mp3 -o songs/ --inspect   # same from the command line, saving every stage's output
tabscribe watch songs/song.atex # open one file in the app
tabscribe render songs/song.atex  # print it as plain-text tab
```

No models installed yet? `-c examples/fake.toml` runs everything with stand-ins.

## How good is it?

`tabscribe eval` renders reference tabs to audio with known notes and scores each stage. With perfectly separated stems, the finished tab scores 0.82–1.00 (F1: right pitch at the right grid position) for guitar and 0.80–0.98 for bass across the four test songs, and drum hits 0.98. Fingering sometimes differs from the reference (a playable alternative), which is what the Claude Code loop is for. These are synthetic recordings; real ones will be harder. Details in [evals/README.md](evals/README.md).

## Architecture

Every stage is an interface with fixed inputs and outputs, and a TOML config decides which implementation fills it, so a different model is a config change. One end-to-end model can replace several stages. See [docs/architecture.md](docs/architecture.md) for the layers, glossary and stage contracts, and `tabscribe stages` to see what's wired where.

## Notes

- Basic Pitch is licensed CC BY-NC 4.0 (non-commercial).
- Demucs downloads its weights on first use from Meta's servers.
- The app serves alphaTab from `node_modules`; without `npm install` it falls back to the jsDelivr CDN.
