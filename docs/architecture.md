# Architecture

tabscribe turns a recording into editable tabs. The code is split into layers so that any stage (the model that separates instruments, the one that hears notes, the logic that picks frets) can be replaced without touching the others.

## The idea in one picture

```
            ┌──────────────────────────────────────────────┐
            │  interfaces   cli.py, watch.py (and later    │
            │               a web app)                     │
            └───────────────┬──────────────────────────────┘
                            │ calls
            ┌───────────────▼──────────────────────────────┐
            │  application  pipeline.py: the use case      │
            │               ports.py:    stage contracts   │
            │               config.py:   which adapter     │
            │                            fills which stage │
            └───────┬───────────────────────▲──────────────┘
                    │ uses                  │ implement
            ┌───────▼───────┐       ┌───────┴──────────────┐
            │  domain       │◄──────│  adapters            │
            │  plain data:  │ use   │  Demucs, Basic Pitch,│
            │  notes, beats,│       │  madmom, fretting,   │
            │  songs        │       │  alphaTex writer, …  │
            └───────────────┘       └──────────────────────┘
```

Dependencies only point inward. The domain imports nothing; the application imports the domain; adapters import both. So a new model never forces a change to the pipeline, and the pipeline never knows which model it's running.

## Layers

**Domain** (`src/tabscribe/domain/`): the vocabulary of the problem as plain Python data, with no libraries. It has two time domains, and keeping them apart is the main modelling decision:

- *Performance time* (seconds): what the models heard. Timing is imprecise, because players and models are.
- *Score time* (ticks, 48 per beat): what gets written down. Everything sits on a grid.

The quantizer is the only stage that converts between the two.

**Application** (`src/tabscribe/application/`): what the program does, without saying how.
- `ports.py` defines one interface per stage: its inputs, its outputs and its rules.
- `pipeline.py` runs the stages in order, talking only to those interfaces.
- `config.py` reads a TOML file and decides which adapter fills each stage.
- `inspect.py` saves every stage's output as JSON, to see what each step did.

**Adapters** (`src/tabscribe/adapters/`): concrete implementations of the ports, grouped by kind: `ml/` (models), `quantize/`, `fretting/`, `notation/` (writers), `testing/` (fakes).

**Interfaces** (`cli.py`, `watch.py`): ways in for a person. A web app would be another one, calling the same pipeline.

## Glossary

| Term | Meaning |
|---|---|
| Mix | The original recording, all instruments together |
| Stem | One instrument isolated from the mix |
| Role | What an instrument does: guitar, bass, drums, piano, vocals, other. Also names a stem |
| Instrument | A part to transcribe: a role, a display name and (if fretted) a tuning |
| Tuning | Open-string pitches, highest string first. String 1 is the highest |
| Rhythm | The beat grid of the recording: tempo, meter, beat and downbeat times |
| Harmony | Key and chord segments, in seconds |
| NoteEvent / DrumHit | One note or drum hit as heard, in seconds |
| Track | All events for one instrument, in seconds (`PitchedTrack`, `DrumTrack`) |
| Tick | Score time unit; 48 per beat |
| ScoreNote / ScoreHit | A note or hit placed on the grid, in ticks. A ScoreNote gains a string and fret when fretted |
| Part | All notes for one instrument, in ticks (`PitchedPart`, `DrumPart`) |
| Song | The aggregate: title, tempo, meter, chord symbols and parts. What writers and editors work on |

"Track" always means seconds and "Part" always means ticks.

## Stage contracts

Each stage is a Python `Protocol` in `application/ports.py`. An adapter fits a stage if it has the right method; it doesn't need to inherit from anything. Adapters must not change their inputs.

| # | Stage | Input | Output | Default adapter | Rules |
|---|---|---|---|---|---|
| 1 | **SourceSeparator** | mix, roles wanted, work folder | a stem per role it can produce | Demucs `htdemucs_6s` | may skip roles it can't produce |
| 2 | **RhythmAnalyzer** | mix | Rhythm | madmom | should report every beat time so drift is followed |
| 3 | **HarmonyAnalyzer** (optional) | mix, Rhythm | Harmony | madmom | chord labels like `Am`, `G7`; `N` for no chord |
| 4a | **PitchTranscriber** | one stem, Instrument | NoteEvents | Basic Pitch | unquantised and unfretted; may use the instrument to limit range |
| 4b | **DrumTranscriber** | drum stem | DrumHits | ADTOF (not written yet) | pieces as General MIDI keys |
| 4* | **MixTranscriber** (alternative to 1 + 4a + 4b) | mix, Instruments | Tracks | MuScriptor (not written yet) | the slot for end-to-end models |
| 5 | **Quantizer** | Tracks, Rhythm, Harmony, title | Song (unfretted) | grid | the only stage that converts seconds to ticks |
| 6 | **FretAssigner** | a part's notes, Tuning | the same notes with string and fret | min-movement | keep positions already set; leave unplayable notes unfretted |
| 7 | **Refiner** (zero or more) | Song | Song | none | any cleanup: ghost notes, hammer-on detection, an LLM pass |
| 8 | **SongWriter** | Song | text | alphaTex, plain-text tab | `extension` names the file type |

Stages 1 to 4 deal with audio and seconds. Stages 5 onward deal with the score. Rhythm and harmony are read once from the mix and passed along.

## Changing a component

Pick the stage, write a class with that stage's method, and point the config at it:

```toml
# my.toml
[stages]
pitch = "my_models.guitar:GuitarTranscriber"   # any importable "module:Class"

[adapters."my_models.guitar:GuitarTranscriber"]
checkpoint = "weights/v3.pt"                  # passed to the constructor
```

```bash
tabscribe stages -c my.toml                 # check what's wired where
tabscribe tab song.mp3 -c my.toml --inspect # run, saving every stage's output
```

To replace several stages with one end-to-end model, fill `mix_transcriber`. The separator and per-stem transcribers are then skipped:

```toml
[stages]
mix_transcriber = "muscriptor"
```

To add an AI cleanup pass (for example an LLM that tidies the tab), write a `Refiner` and list it:

```toml
[stages]
refiners = ["my_models.cleanup:LlmTabCleaner"]
```

`tests/test_contracts.py` checks that every adapter satisfies its port and that the pipeline gives the same result whether it runs modular or end-to-end. Add your adapter to the parametrised list there.

## Seeing what each stage does

```bash
tabscribe tab song.mp3 --inspect -o out/
ls out/stages/
# 1_rhythm.json  2_harmony.json  3_tracks.json
# 4_quantized.json  5_fretted.json  6_refined.json
```

Comparing `3_tracks.json` (seconds, as heard) with `4_quantized.json` (ticks, on the grid) shows what quantizing changed; `4` against `5` shows the fret choices.

`examples/fake.toml` runs the whole pipeline with fake models, so all of this works before any model is installed.

## Status

| Part | State |
|---|---|
| Domain, ports, pipeline, config, inspection | done, tested |
| Quantizer (grid), fret assigner (min-movement) | done, tested |
| alphaTex and plain-text writers | done, tested; alphaTex validated against alphaTab 1.9 |
| Demucs, Basic Pitch, madmom adapters | written against their documented APIs, not yet run |
| ADTOF, MuScriptor adapters | placeholders |
| Web interface (Guitar Pro style) | planned; would build on the alphaTab preview |
