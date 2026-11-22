"""MixTranscriber using MuScriptor (Kyutai / Mirelo).

Model: an open multi-instrument audio-to-MIDI model. It takes the full mix
and returns notes already grouped by instrument, so it replaces the
separator and both per-stem transcribers in one stage.
Status: not implemented. Fill in `transcribe` once the model's API is checked.
"""

from __future__ import annotations

from collections.abc import Sequence

from ...domain import AudioRef, Instrument, Track


class MuScriptorTranscriber:
    def transcribe(self, mix: AudioRef, instruments: Sequence[Instrument]) -> list[Track]:
        raise NotImplementedError(
            "MuScriptor adapter not written yet. It must map the model's instrument "
            "tracks onto the requested instruments: a PitchedTrack of NoteEvents for "
            "guitar/bass, a DrumTrack of DrumHits for drums."
        )
