# tabscribe

Turn a recording into tabs for guitar, bass and drums, then clean them up by prompting Claude Code instead of editing by hand.

## How it works

1. `tabscribe tab song.mp3` runs a pipeline of models (separate instruments, find the beat and chords, hear the notes, pick frets) and writes `song.atex`.
2. `tabscribe watch song.atex` opens a live preview in the browser, with playback.
3. In Claude Code, in this folder, you say what's wrong: *"bar 2 should be in 7th position"*, *"those are hammer-ons"*, *"add a crash on the first beat"*. It edits the file, the preview redraws.

The `.atex` file is alphaTex, a plain-text music notation format, so Claude Code can edit it like code. `CLAUDE.md` tells it the rules.

## Try it without any models

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
tabscribe tab any.wav -c examples/fake.toml --inspect -o out/   # fake models, audio isn't read
tabscribe watch out/any.atex
```

`out/stages/` then holds the output of every stage as JSON.

## Architecture

Every stage is an interface with fixed inputs and outputs, and a config file decides which implementation fills it. To try a different model, write a class with the stage's method and name it in the config; nothing else changes. One end-to-end model can also replace several stages at once.

See [docs/architecture.md](docs/architecture.md) for the layers, the glossary and the contract for each stage.

```bash
tabscribe stages              # which adapter fills each stage
tabscribe stages -c my.toml   # same, with your config
```

## Status

- Working and tested: domain model, pipeline, config, grid quantizer, fret assignment, alphaTex and plain-text writers, live preview.
- Written but not yet run: Demucs, Basic Pitch and madmom adapters (`pip install -e ".[ml]"`).
- Placeholders: ADTOF (drums) and MuScriptor (end-to-end).
- Later: a Guitar Pro-style web interface built on the preview.

## Notes

- Basic Pitch is licensed CC BY-NC 4.0 (non-commercial).
- The preview loads alphaTab from the jsDelivr CDN, so it needs internet access.
- `npm install` once to enable `scripts/check_atex.mjs` (validates `.atex` files) and the alphaTab test.
