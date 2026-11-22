# Evals

`tabscribe eval` scores a pipeline configuration against reference tabs, stage by stage, so you can tell which component is responsible when the output is wrong, and whether swapping one in made things better.

## How it works

Each file in `cases/` is a correct tab in alphaTex. For each one:

1. **Render.** The tab is played back with human-like timing (a few ms early or late, strums spread across ~20 ms, varying loudness) and rendered with FluidSynth and the FluidR3 General MIDI soundfont, one audio file per instrument plus the mix. The notes actually played are the answer key.
2. **Transcribe.** The configured pipeline runs on the mix, keeping every stage's output.
3. **Score.** Each stage is compared with the truth using standard music-research measures (`mir_eval`): notes and drum hits must start within 50 ms, beats within 70 ms.

Two stages are also scored alone with perfect input: the quantizer gets the true performance and beats, the fret assigner gets the true notes without frets. If the full pipeline does badly but these do well, the problem is upstream.

By default the separator is replaced with the perfectly separated stems (`folder_stems`), which isolates the transcription models. Pass a config with `separator = "demucs"` to include separation.

```bash
uv sync --extra ml --extra evals
sudo apt install fluidsynth fluid-soundfont-gm   # or: brew install fluid-synth
npm install
uv run tabscribe eval                         # all cases, default models
uv run tabscribe eval --only riff16 --seed 3  # one case, different timing/velocity variation
uv run tabscribe eval -c my.toml              # try a different model in some stage
```

Results go to `out/evals/`: `summary.md` (the table below), `results.json` (everything), and per case `result.atex`, `result.txt` and `reference.txt` to compare by eye.

## Reading the numbers

- **F1** combines precision (of what was output, how much is right) and recall (of what's really there, how much was found). 1.00 is perfect.
- **notes F1**: the transcription model alone, in seconds.
- **final tab notes F1**: right pitch on the right grid position in the finished tab.
- **same string/fret**: of the right notes, how many are fingered like the reference. Different but playable fingerings count as wrong here, so read this one loosely.

## Current results

Default models (Basic Pitch, ADTOF, madmom) with perfect stems, on two different random variations (seed 0 / seed 7), November 2026:

| stage | arpeggios | lead | riff16 | strum |
|---|---|---|---|---|
| guitar: final tab notes F1 | 0.98 / 0.97 | 1.00 / 0.91 | 0.94 / 0.91 | 0.82 / 0.85 |
| bass: final tab notes F1 | 0.91 / 0.80 | 0.94 / 0.86 | 0.95 / 0.98 | 0.80 / 0.80 |
| drums: hits F1 | 0.98 / 0.98 | 0.98 / 0.98 | 0.99 / 0.98 | 0.98 / 0.98 |
| guitar: same string/fret | 1.00 / 1.00 | 1.00 / 1.00 | 0.49 / 0.49 | 0.79 / 0.97 |
| chords (time correct) | 0.74 / 0.74 | 0.47 / 0.47 | 0.92 / 0.80 | 0.91 / 0.93 |

What changed to get here (before → after, seed 0): guitar final tab 0.69 / 0.94 / 0.06 / 0.17 → 0.98 / 1.00 / 0.94 / 0.82.

- Basic Pitch reports overtones as extra quiet notes; the adapter now removes them (`overtone_ratio`) and drops faint ghosts (`relative_floor`). Note F1 averaged 0.62 → 0.87.
- madmom doubled the tempo of the half-time strum (182 instead of 90 bpm); the tempo search is now limited to 55–170 bpm by default.
- madmom sometimes puts beat 1 on beat 3, or every beat on the off-beat. The quantizer now corrects both, using chord changes, kick and snare hits, and where the music starts.

## Known gaps

- **Fingering style.** On the riff the fret assigner picks open position where the reference uses the 5th-position box. Both are playable; this is what "play this in 5th position" in Claude Code is for.
- **Synthetic audio.** These are rendered, not recorded, and short. Real recordings (amp tone, room, bends, mistakes) will score lower. Real datasets with note-level annotations (GuitarSet, GOAT, Slakh2100) can be added as cases once converted to `.atex`; they couldn't be downloaded in the environment where this was built.
- **Few cases.** Four songs, so a single tuning decision can overfit. Add cases before tuning further.

## Adding a case

Write the correct tab as an `.atex` file in `cases/` (any instruments, any length) and check it parses with `node scripts/check_atex.mjs cases/new.atex`. The instrument named in `\track "..." { instrument "..." }` picks the General MIDI sound used to render it.
