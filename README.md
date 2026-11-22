# tabscribe

An open-source take on Transcribe!: a practice player for working out music by ear, plus an automatic audio → guitar tab draft (Guitar Pro / MusicXML).

## Goals

**Player (the Transcribe! part)**
- Slow down audio without changing pitch (Rubber Band)
- A–B looping, markers for sections/bars
- EQ / band filtering to isolate parts
- Constant-Q spectrum view showing which notes are sounding

**Auto-tab (the experimental part)**
1. **Separate** – isolate guitar from the mix (Demucs v4)
2. **Analyse** – key, chords, beats and downbeats (madmom)
3. **Transcribe** – audio → MIDI notes (Basic Pitch)
4. **Fret** – assign each note a playable string/fret
5. **Export** – `.gp5` (PyGuitarPro), MusicXML, MIDI, ASCII tab

The output is meant as a draft to fix in Guitar Pro / TuxGuitar, not a finished tab.

## Status

Scaffold only. Stages live in `src/tabscribe/pipeline.py` as stubs.

## Notes

- Basic Pitch is licensed CC BY-NC 4.0 (non-commercial). Fine for a hobby project; swap it out if this ever becomes a product.
- Prior art worth reading: `aguilasa/tabgen`, `bmcdonald3/AutoTab`, `JackJamesLoth/Audio2Tab`.

## Dev

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
tabscribe --help
```
