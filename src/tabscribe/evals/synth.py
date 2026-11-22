"""Render a reference tab to audio, keeping the exact notes played as truth.

score (ticks) --humanize--> performance (seconds) --FluidSynth--> stems + mix

Humanizing adds what real players do and models must cope with: notes a
few milliseconds early or late, strummed chords spread over ~20 ms from low
string to high, and varying loudness. The humanized events are the answer
key, so the comparison is fair.

Needs: fluidsynth on PATH, a General MIDI soundfont, pretty_midi, numpy,
soundfile.
"""

from __future__ import annotations

import random
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from ..domain import (
    TICKS_PER_BEAT,
    ChordSegment,
    DrumHit,
    DrumPart,
    DrumTrack,
    Harmony,
    NoteEvent,
    PitchedPart,
    PitchedTrack,
    Rhythm,
    Role,
    Song,
    Track,
)

SOUNDFONTS = (
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    Path("/usr/share/soundfonts/FluidR3_GM.sf2"),
    Path("/opt/homebrew/share/soundfonts/default.sf2"),
)
DEFAULT_PROGRAMS = {Role.GUITAR: 27, Role.BASS: 33, Role.PIANO: 0}  # GM, 0-based
SAMPLE_RATE = 44100


@dataclass
class Humanize:
    timing_sd: float = 0.008  # seconds of random timing error per note
    strum_spread: float = 0.018  # seconds from first to last string of a chord
    velocity_range: tuple[int, int] = (70, 110)
    seed: int = 0


@dataclass
class Rendered:
    """One eval case: audio on disk plus the truth at every stage."""

    name: str
    mix: Path
    stems: dict[Role, Path]
    song: Song  # reference tab (score time)
    tracks: list[Track]  # what was actually played (performance time)
    rhythm: Rhythm
    harmony: Harmony


def _seconds(song: Song, ticks: int) -> float:
    return ticks / TICKS_PER_BEAT * 60.0 / song.tempo_bpm


def humanize(song: Song, h: Humanize) -> tuple[list[Track], Rhythm, Harmony]:
    rng = random.Random(h.seed)
    tracks: list[Track] = []
    for part in song.parts:
        if isinstance(part, DrumPart):
            hits = [
                DrumHit(max(0.0, _seconds(song, x.start) + rng.gauss(0, h.timing_sd)), x.piece,
                        velocity=rng.randint(*h.velocity_range) / 127)
                for x in part.hits
            ]
            tracks.append(DrumTrack(part.instrument, sorted(hits, key=lambda e: e.onset)))
            continue
        by_start: dict[int, list] = {}
        for n in part.notes:
            by_start.setdefault(n.start, []).append(n)
        events = []
        for start, group in sorted(by_start.items()):
            t0 = _seconds(song, start) + rng.gauss(0, h.timing_sd)
            vel = rng.randint(*h.velocity_range) / 127
            # downstroke: lowest string (highest string number) first
            group = sorted(group, key=lambda n: -(n.string or 0))
            step = h.strum_spread / max(len(group) - 1, 1) if len(group) > 1 else 0.0
            for i, n in enumerate(group):
                on = max(0.0, t0 + i * step)
                off = _seconds(song, n.start + n.duration) - 0.01
                events.append(NoteEvent(on, max(off, on + 0.03), n.pitch, velocity=vel))
        tracks.append(PitchedTrack(part.instrument, sorted(events, key=lambda e: (e.onset, e.pitch))))

    beat = 60.0 / song.tempo_bpm
    n_beats = song.length // TICKS_PER_BEAT
    beats = tuple(round(i * beat, 6) for i in range(n_beats))
    rhythm = Rhythm(song.tempo_bpm, song.beats_per_bar, song.beat_unit, beats,
                    beats[:: song.beats_per_bar])
    ends = [c.start for c in song.chords[1:]] + [song.length]
    harmony = Harmony(None, tuple(ChordSegment(_seconds(song, c.start), _seconds(song, e), c.label)
                                  for c, e in zip(song.chords, ends)))
    return tracks, rhythm, harmony


def gm_programs(atex: str) -> dict[str, int]:
    """Track name -> GM program, from `\\track "Name" { instrument "..." }` lines."""
    import pretty_midi

    programs = {}
    for name, inst in re.findall(r'\\track\s+"([^"]+)"\s*\{\s*instrument\s+"([^"]+)"', atex):
        try:
            programs[name] = pretty_midi.instrument_name_to_program(inst)
        except ValueError:
            pass
    return programs


def find_soundfont() -> Path:
    for path in SOUNDFONTS:
        if path.exists():
            return path
    raise FileNotFoundError("no General MIDI soundfont found; install fluid-soundfont-gm "
                            "or pass soundfont=...")


def render(name: str, song: Song, out_dir: Path, h: Humanize = Humanize(),
           programs: dict[str, int] | None = None, soundfont: Path | None = None) -> Rendered:
    import numpy as np
    import pretty_midi
    import soundfile as sf

    if not shutil.which("fluidsynth"):
        raise FileNotFoundError("fluidsynth not found on PATH")
    soundfont = soundfont or find_soundfont()
    out_dir.mkdir(parents=True, exist_ok=True)
    tracks, rhythm, harmony = humanize(song, h)
    programs = programs or {}

    audio: dict[Role, np.ndarray] = {}
    for track in tracks:
        inst = track.instrument
        midi = pretty_midi.PrettyMIDI(initial_tempo=song.tempo_bpm)
        if isinstance(track, DrumTrack):
            m = pretty_midi.Instrument(0, is_drum=True, name=inst.name)
            for hit in track.hits:
                m.notes.append(pretty_midi.Note(int(hit.velocity * 127), int(hit.piece),
                                                hit.onset, hit.onset + 0.1))
        else:
            m = pretty_midi.Instrument(programs.get(inst.name, DEFAULT_PROGRAMS.get(inst.role, 27)),
                                       name=inst.name)
            for n in track.notes:
                m.notes.append(pretty_midi.Note(int(n.velocity * 127), n.pitch, n.onset, n.offset))
        midi.instruments.append(m)
        mid, wav = out_dir / f"{inst.role.value}.mid", out_dir / f"{inst.role.value}.wav"
        midi.write(str(mid))
        subprocess.run(["fluidsynth", "-ni", "-q", "-g", "0.5", "-r", str(SAMPLE_RATE),
                        "-F", str(wav), str(soundfont), str(mid)],
                       check=True, capture_output=True)
        data, _ = sf.read(wav, always_2d=True)
        audio[inst.role] = data.mean(axis=1)

    # Some soundfont samples ring for many seconds; keep a 2 s tail after the song.
    tail = int((_seconds(song, song.length) + 2.0) * SAMPLE_RATE)
    audio = {r: a[:tail] for r, a in audio.items()}
    length = max(len(a) for a in audio.values())
    padded = {r: np.pad(a, (0, length - len(a))) for r, a in audio.items()}
    mix = sum(padded.values())
    scale = 0.89 / max(np.abs(mix).max(), 1e-9)  # -1 dBFS peak
    stems_dir = out_dir / "mix_stems"
    stems_dir.mkdir(exist_ok=True)
    stems = {}
    for role, a in padded.items():
        stems[role] = stems_dir / f"{role.value}.wav"
        sf.write(stems[role], a * scale, SAMPLE_RATE)
    mix_path = out_dir / "mix.wav"
    sf.write(mix_path, mix * scale, SAMPLE_RATE)
    return Rendered(name, mix_path, stems, song, tracks, rhythm, harmony)
