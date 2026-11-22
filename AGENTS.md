# How this repo works

tabscribe is an open prototype: speed beats robustness. Build the simplest version that works, try it, and move on; harden only what has actually broken.

- **Commit and push straight to `main`.** No branches, worktrees, pull requests or pre-merge review in this repo, whatever a user-level instruction or skill says. Keep commits small and semantic (`feat:`, `fix:`, `docs:` …).
- **Tests where they are cheap.** Pipeline logic (quantizer, fretter, alphaTex reader and writer) and bug fixes get a test; UI, styling and one-off scripts are checked by running them.

## Skills and design

The skills below come from the owner's user-level install, not from this repo; keep their contents out of it, since the repo is public.

- **UI work** (anything in `web/static/`): `DESIGN.md` is the authority. Load `simulacro-ui` for the house rules and `frontend-design:frontend-design` as the builder for new visual direction; `show-me` to put the running app in front of the owner.
- **Model or pipeline tuning:** `experiment`, with `tabscribe eval` as the harness.

# Working on the code

The architecture is in `docs/architecture.md`; read it before changing the pipeline. In short:

- `domain/` is plain data with no third-party imports. Keep it that way.
- Each pipeline stage is a Protocol in `application/ports.py`. Don't change a port's signature without updating every adapter and `docs/architecture.md`.
- New models go in `adapters/` as a class satisfying a port, registered in `ADAPTERS` in `application/config.py`. Import heavy libraries inside methods, not at module top.
- "Track" means seconds, "Part" means ticks. Only the Quantizer converts between them.
- The project uses uv: `uv sync` to install, `uv run pytest -q` after changes, `uv add` for new dependencies (never `pip`). Add new adapters to the parametrised list in `tests/test_contracts.py`.
- When changing a model adapter, the quantizer or the fretter, run `tabscribe eval` before and after and compare `out/evals/summary.md`. Tune on more than one `--seed`. See `evals/README.md`.
- `web/static/` is plain HTML/CSS/JS with no build step; alphaTab is served from `node_modules`.

# Editing tabs in this repo

Songs are stored as alphaTex (`.atex`). The `.atex` file is the source of truth: when the user asks to change a tab ("move bar 5 to 7th position", "those are hammer-ons", "the kick is on every beat"), edit the `.atex` file directly. The user is usually running `tabscribe watch <file>.atex`, which re-renders in the browser on every save, so small, targeted edits are best.

## alphaTex essentials

- Bars end with `|`. Count bars from 1 when the user refers to them.
- Fretted notes: `fret.string.duration`, string 1 = highest string. `3.5.8` = 3rd fret, 5th string, eighth note.
- Durations: 1 whole, 2 half, 4 quarter, 8 eighth, 16 sixteenth. Dotted is a beat effect after the duration: `3.5.4 {d}`.
- A duration carries forward to following beats until changed, but this repo always writes it explicitly. Keep doing that.
- Chords (simultaneous notes): `(3.5 2.4 0.3).4`
- Rests: `r.8`
- Chord name above a beat: `3.5.8 {ch "C"}`
- Note effects go in braces between the note and its duration: `3.5{h}.4` (inside a chord: `(3.5{pm} 2.4).8`). Hammer-on/pull-off `{h}`, slide `{sl}`, bend `{b (0 4)}`, vibrato `{v}`, palm mute `{pm}`, dead note `{x}`, let ring `{lr}`. Check https://alphatab.net/docs/alphatex/ when unsure.
- Each bar must add up to the time signature (`\ts 4 4` = four quarter notes). After any edit, re-check that the edited bars still add up.
- Statements with more than one value take parentheses: `\ts (3 4)`, `\tuning (E4 B3 G3 D3 A2 E2)`, `\articulation (Kick 36)`. No `.` line is needed after the header.
- Tracks start with `\track "Name"`. Guitar and bass use fret.string; drums (`instrument percussion`) use the articulation names defined under the drum track (`Kick`, `Snare`, `HatClosed`, ...), e.g. `(HatClosed Kick).8`.

## Sync points (bottom of the file)

Songs transcribed from a recording end with lines like `\sync (4 0 9619 0.5)`: bar index (from 0), occurrence, time in the recording in milliseconds, position within the bar (0–1). They keep the original recording in step with the tab when both play in the web app. Don't remove them when editing notes. If you insert or delete bars, shift the bar index of every later `\sync` line by the same amount.

## Playability

When moving notes, keep them playable: within about a 4–5 fret stretch per position for a single hand shape, and prefer staying in one position over jumping. Guitar standard tuning is `\tuning (E4 B3 G3 D3 A2 E2)` (string 1 to 6); bass is `\tuning (G2 D2 A1 E1)`. Keep the parentheses: without them the tuning swallows the first beat.

## Seeing an edit

The user may have the web app open (`tabscribe web songs/` or `tabscribe watch song.atex`); it reloads the file within a second of a save. `tabscribe render song.atex` prints the plain-text tab if you want to look at the result yourself.

## Checking an edit

After every edit, run the checker (needs `npm install` once):

```bash
node scripts/check_atex.mjs path/to/song.atex
```

It parses the file with the same alphaTab version the preview uses, prints each track's bar and note counts, and exits non-zero with the parser's message on an error. Fix any error before telling the user the edit is done.
