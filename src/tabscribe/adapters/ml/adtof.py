"""DrumTranscriber using ADTOF (Zehren et al.), PyTorch port by xavriley.

Model: a frame-level CNN+RNN trained on real drum recordings. It detects
five classes: kick, snare, toms, hi-hat and cymbals (crash and ride are one
class), so this adapter reports cymbals as crash and toms as the low tom.
Install: pip install torch "adtof-pytorch @ git+https://github.com/xavriley/ADTOF-pytorch"
Weights ship inside the package.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from ...domain import AudioRef, DrumHit, DrumPiece

# ADTOF's General MIDI output keys -> our drum pieces
ADTOF_TO_PIECE = {
    35: DrumPiece.KICK,
    36: DrumPiece.KICK,
    38: DrumPiece.SNARE,
    47: DrumPiece.TOM_LOW,
    42: DrumPiece.HAT_CLOSED,
    49: DrumPiece.CRASH,
}


class AdtofDrums:
    def __init__(self, threshold: float | None = None, device: str = "cpu"):
        self.threshold = threshold
        self.device = device

    def transcribe(self, stem: AudioRef) -> list[DrumHit]:
        import pretty_midi
        from adtof_pytorch import transcribe_to_midi  # heavy import, only when used

        with tempfile.TemporaryDirectory() as tmp:
            midi_path = Path(tmp) / "drums.mid"
            transcribe_to_midi(str(stem.path), str(midi_path), threshold=self.threshold,
                               device=self.device)
            midi = pretty_midi.PrettyMIDI(str(midi_path))

        hits = []
        for inst in midi.instruments:
            for note in inst.notes:
                piece = ADTOF_TO_PIECE.get(note.pitch)
                if piece is not None:
                    hits.append(DrumHit(float(note.start), piece, velocity=note.velocity / 127))
        return sorted(hits, key=lambda h: (h.onset, h.piece))
