"""DrumTranscriber using ADTOF (Zehren et al.).

Model: a drum transcription network trained on real recordings; outputs
kick, snare, hi-hat, toms and cymbals as General MIDI keys.
Candidate package: adtof-plus-drum-transcription.
Status: not implemented. Fill in `transcribe` once the package API is checked.
"""

from __future__ import annotations

from ...domain import AudioRef, DrumHit


class AdtofDrums:
    def transcribe(self, stem: AudioRef) -> list[DrumHit]:
        raise NotImplementedError(
            "ADTOF adapter not written yet. It must return DrumHit(onset_seconds, "
            "DrumPiece.from_midi(gm_key), velocity) for every hit, sorted by onset."
        )
