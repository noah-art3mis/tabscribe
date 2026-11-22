"""Domain model. Pure Python, no third-party imports.

Two time domains:
- performance (seconds): what the models heard -> domain.performance
- score (ticks): what gets written and edited  -> domain.score
"""

from .audio import AudioRef, StemSet
from .instruments import (
    BASS_STANDARD,
    GUITAR_STANDARD,
    DrumPiece,
    Instrument,
    Role,
    Tuning,
    bass,
    drums,
    guitar,
    pitch_name,
)
from .performance import (
    ChordSegment,
    DrumHit,
    DrumTrack,
    Harmony,
    NoteEvent,
    PitchedTrack,
    Track,
)
from .rhythm import TICKS_PER_BEAT, Rhythm, Seconds, Ticks
from .score import ChordSymbol, DrumPart, Part, PitchedPart, ScoreHit, ScoreNote, Song

__all__ = [
    "AudioRef", "StemSet",
    "BASS_STANDARD", "GUITAR_STANDARD", "DrumPiece", "Instrument", "Role", "Tuning",
    "bass", "drums", "guitar", "pitch_name",
    "ChordSegment", "DrumHit", "DrumTrack", "Harmony", "NoteEvent", "PitchedTrack", "Track",
    "TICKS_PER_BEAT", "Rhythm", "Seconds", "Ticks",
    "ChordSymbol", "DrumPart", "Part", "PitchedPart", "ScoreHit", "ScoreNote", "Song",
]
