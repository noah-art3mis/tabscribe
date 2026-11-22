"""Scores for each stage, against the truth from synth.render.

Standard music-information-retrieval measures via mir_eval, with the usual
tolerances: 50 ms for note and drum onsets, 70 ms for beats.

Precision: of what the model output, how much was right.
Recall: of what was really there, how much the model found.
F1: one number combining both (their harmonic mean).
"""

from __future__ import annotations

from collections.abc import Sequence

from ..domain import DrumHit, DrumPiece, Harmony, NoteEvent, Rhythm, ScoreNote

ONSET_TOLERANCE = 0.05

# Drum pieces grouped into the classes most drum models (e.g. ADTOF) predict.
DRUM_CLASSES = {
    "kick": {DrumPiece.KICK},
    "snare": {DrumPiece.SNARE, DrumPiece.STICK},
    "toms": {DrumPiece.TOM_LOW, DrumPiece.TOM_HIGH, DrumPiece.TOM_FLOOR},
    "hihat": {DrumPiece.HAT_CLOSED, DrumPiece.HAT_OPEN, DrumPiece.HAT_PEDAL},
    "cymbals": {DrumPiece.CRASH, DrumPiece.RIDE, DrumPiece.RIDE_BELL},
}


def _prf(tp: int, n_est: int, n_ref: int) -> dict[str, float]:
    p = tp / n_est if n_est else 0.0
    r = tp / n_ref if n_ref else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f, "n_ref": n_ref, "n_est": n_est}


def notes(ref: Sequence[NoteEvent], est: Sequence[NoteEvent]) -> dict[str, float]:
    """Note onset + pitch match within 50 ms (offsets ignored, as is standard)."""
    import numpy as np
    from mir_eval.transcription import precision_recall_f1_overlap
    from mir_eval.util import midi_to_hz

    if not ref or not est:
        return _prf(0, len(est), len(ref))
    ri = np.array([[n.onset, max(n.offset, n.onset + 1e-3)] for n in ref])
    ei = np.array([[n.onset, max(n.offset, n.onset + 1e-3)] for n in est])
    rp = midi_to_hz(np.array([n.pitch for n in ref], dtype=float))
    ep = midi_to_hz(np.array([n.pitch for n in est], dtype=float))
    p, r, f, _ = precision_recall_f1_overlap(ri, rp, ei, ep, onset_tolerance=ONSET_TOLERANCE,
                                             offset_ratio=None)
    return {"precision": p, "recall": r, "f1": f, "n_ref": len(ref), "n_est": len(est)}


def drums(ref: Sequence[DrumHit], est: Sequence[DrumHit]) -> dict[str, dict[str, float]]:
    """Per drum class, plus 'all' summed over classes."""
    import numpy as np
    from mir_eval.util import match_events

    out, tp_all, ref_all, est_all = {}, 0, 0, 0
    for name, pieces in DRUM_CLASSES.items():
        r = np.array(sorted(h.onset for h in ref if h.piece in pieces))
        e = np.array(sorted(h.onset for h in est if h.piece in pieces))
        if len(r) == 0 and len(e) == 0:
            continue
        tp = len(match_events(r, e, ONSET_TOLERANCE)) if len(r) and len(e) else 0
        out[name] = _prf(tp, len(e), len(r))
        tp_all, ref_all, est_all = tp_all + tp, ref_all + len(r), est_all + len(e)
    out["all"] = _prf(tp_all, est_all, ref_all)
    return out


def beats(ref: Rhythm, est: Rhythm) -> dict[str, float]:
    import numpy as np
    from mir_eval.beat import f_measure

    f = f_measure(np.array(ref.beat_times), np.array(est.beat_times)) if est.beat_times else 0.0
    return {
        "beat_f1": f,
        "tempo_ref": ref.tempo_bpm,
        "tempo_est": est.tempo_bpm,
        "tempo_error_pct": 100 * abs(est.tempo_bpm - ref.tempo_bpm) / ref.tempo_bpm,
        "meter_ok": float(est.beats_per_bar == ref.beats_per_bar),
    }


def _harte(label: str) -> str:
    """'Am' -> 'A:min', 'C' -> 'C:maj', 'G7' -> 'G:7', 'N' -> 'N'."""
    if label in ("N", "X", ""):
        return "N"
    root = label[:2] if len(label) > 1 and label[1] in "#b" else label[:1]
    rest = label[len(root):]
    quality = {"": "maj", "m": "min", "7": "7", "m7": "min7", "maj7": "maj7",
               "dim": "dim", "aug": "aug", "sus4": "sus4", "sus2": "sus2"}.get(rest, rest or "maj")
    return f"{root}:{quality}"


def chords(ref: Harmony, est: Harmony) -> dict[str, float]:
    """Share of time with the right chord (major/minor level, as in MIREX)."""
    import numpy as np
    from mir_eval import chord
    from mir_eval.util import adjust_intervals, intervals_to_durations, merge_labeled_intervals

    if not ref.chords:
        return {}
    if not est.chords:
        return {"majmin_accuracy": 0.0}
    ri = np.array([[c.start, c.end] for c in ref.chords])
    ei = np.array([[c.start, c.end] for c in est.chords])
    rl = [_harte(c.label) for c in ref.chords]
    el = [_harte(c.label) for c in est.chords]
    ei, el = adjust_intervals(ei, el, ri.min(), ri.max(), chord.NO_CHORD, chord.NO_CHORD)
    intervals, rl2, el2 = merge_labeled_intervals(ri, rl, ei, el)
    durations = intervals_to_durations(intervals)
    score = chord.weighted_accuracy(chord.majmin(rl2, el2), durations)
    return {"majmin_accuracy": float(score)}


def score_notes(ref: Sequence[ScoreNote], est: Sequence[ScoreNote]) -> dict[str, float]:
    """Notes in the final tab: same grid position and pitch. Also, of those,
    how many sit on the same string and fret as the reference tab."""
    ref_keys = {(n.start, n.pitch): n for n in ref}
    est_keys = {(n.start, n.pitch): n for n in est}
    matched = ref_keys.keys() & est_keys.keys()
    out = _prf(len(matched), len(est_keys), len(ref_keys))
    fretted = [k for k in matched if ref_keys[k].fretted and est_keys[k].fretted]
    same = sum((ref_keys[k].string, ref_keys[k].fret) == (est_keys[k].string, est_keys[k].fret)
               for k in fretted)
    out["fingering_match"] = same / len(fretted) if fretted else 0.0
    return out
