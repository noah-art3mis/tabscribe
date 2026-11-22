"""Evaluate a pipeline configuration on reference tabs.

For each case (an .atex file with the correct tab):
  1. render it to audio with known notes          (evals.synth)
  2. run the configured pipeline, keeping every stage's output
  3. score each stage against the truth           (evals.metrics)

Two stages are also scored in isolation, fed perfect input, so a bad result
can be traced to the stage that caused it:
  - quantize (oracle): the true performance + true beats -> grid
  - fret (oracle):     the true notes without frets -> fingering
"""

from __future__ import annotations

import json
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from ..adapters.notation.alphatex_reader import AlphaTexReader
from ..application.config import build_pipeline, load_config
from ..domain import AudioRef, DrumPart, DrumTrack, PitchedPart, PitchedTrack
from . import metrics
from .synth import Humanize, gm_programs, render

EVAL_DEFAULTS = """
[stages]
separator = "folder_stems"   # perfect stems from the renderer; use "demucs" to test separation
"""


def _by_role(items):
    return {x.instrument.role: x for x in items}


def evaluate_case(atex: Path, config: dict[str, Any], workdir: Path, humanize: Humanize) -> dict:
    source = atex.read_text()
    truth_song = AlphaTexReader().read(source)
    case = render(atex.stem, truth_song, workdir / atex.stem / "audio", humanize, gm_programs(source))
    pipeline = build_pipeline(config)

    seen: dict[str, Any] = {}
    timings: dict[str, float] = {}
    clock = [time.perf_counter()]

    def observe(stage: str, output: Any) -> None:
        now = time.perf_counter()
        seen[stage], timings[stage] = output, round(now - clock[0], 2)
        clock[0] = now

    song = pipeline.run(AudioRef(case.mix), workdir / atex.stem / "work", case.name, observe)

    result: dict[str, Any] = {"case": case.name, "seconds": timings}
    result["rhythm"] = metrics.beats(case.rhythm, seen["1_rhythm"])
    if pipeline.harmony:
        result["chords"] = metrics.chords(case.harmony, seen["2_harmony"])

    est_tracks = _by_role(seen["3_tracks"])
    for track in case.tracks:
        est = est_tracks.get(track.instrument.role)
        key = f"transcribe_{track.instrument.role.value}"
        if isinstance(track, DrumTrack):
            result[key] = metrics.drums(track.hits, est.hits if est else [])
        else:
            result[key] = metrics.notes(track.notes, est.notes if est else [])

    est_parts = _by_role(song.parts)
    oracle = pipeline.quantizer.quantize(case.tracks, case.rhythm, case.harmony, case.name)
    oracle_parts = _by_role(oracle.parts)
    for part in truth_song.parts:
        if not isinstance(part, PitchedPart):
            continue
        role = part.instrument.role.value
        est = est_parts.get(part.instrument.role)
        result[f"final_tab_{role}"] = metrics.score_notes(part.notes, est.notes if est else [])
        result[f"quantize_oracle_{role}"] = metrics.score_notes(
            part.notes, pipeline.fretter.assign(oracle_parts[part.instrument.role].notes,
                                                part.instrument.tuning))
        unfretted = [replace(n, string=None, fret=None) for n in part.notes]
        result[f"fret_oracle_{role}"] = {
            "fingering_match": metrics.score_notes(
                part.notes, pipeline.fretter.assign(unfretted, part.instrument.tuning)
            )["fingering_match"]
        }

    out = workdir / atex.stem
    from ..adapters.notation.alphatex import AlphaTexWriter
    from ..adapters.notation.ascii_tab import AsciiTabWriter
    (out / "result.atex").write_text(AlphaTexWriter().write(song))
    (out / "result.txt").write_text(AsciiTabWriter().write(song))
    (out / "reference.txt").write_text(AsciiTabWriter().write(truth_song))
    return result


def _fmt(x: float) -> str:
    return f"{x:.2f}"


def summary_table(results: list[dict]) -> str:
    """Markdown table: one row per stage, one column per case."""
    rows: dict[str, dict[str, str]] = {}

    def put(row: str, case: str, value: str) -> None:
        rows.setdefault(row, {})[case] = value

    for r in results:
        c = r["case"]
        put("beats F1", c, _fmt(r["rhythm"]["beat_f1"]))
        put("tempo error %", c, f"{r['rhythm']['tempo_error_pct']:.1f}")
        if "chords" in r and r["chords"]:
            put("chords (time correct)", c, _fmt(r["chords"]["majmin_accuracy"]))
        for key, val in r.items():
            if key.startswith("transcribe_"):
                role = key.removeprefix("transcribe_")
                if "all" in val:
                    put(f"{role}: hits F1", c, _fmt(val["all"]["f1"]))
                    for cls, m in val.items():
                        if cls != "all":
                            put(f"  {cls} F1", c, _fmt(m["f1"]))
                else:
                    put(f"{role}: notes F1", c, _fmt(val["f1"]))
            elif key.startswith("final_tab_"):
                role = key.removeprefix("final_tab_")
                put(f"{role}: final tab notes F1", c, _fmt(val["f1"]))
                put(f"{role}: final tab same string/fret", c, _fmt(val["fingering_match"]))
            elif key.startswith("quantize_oracle_"):
                put(f"{key.removeprefix('quantize_oracle_')}: quantizer alone F1", c, _fmt(val["f1"]))
            elif key.startswith("fret_oracle_"):
                put(f"{key.removeprefix('fret_oracle_')}: fretter alone same string/fret", c,
                    _fmt(val["fingering_match"]))

    cases = [r["case"] for r in results]
    lines = ["| stage | " + " | ".join(cases) + " |", "|---|" + "---|" * len(cases)]
    for row, vals in rows.items():
        lines.append(f"| {row} | " + " | ".join(vals.get(c, "–") for c in cases) + " |")
    return "\n".join(lines)


def main(cases_dir: Path, out: Path, config_path: Path | None, only: list[str] | None,
         seed: int) -> list[dict]:
    import tomllib

    config = load_config(config_path)
    if config_path is None:
        config["stages"].update(tomllib.loads(EVAL_DEFAULTS)["stages"])
    files = sorted(cases_dir.glob("*.atex"))
    if only:
        files = [f for f in files if f.stem in only]
    results = []
    for f in files:
        print(f"evaluating {f.stem} ...", flush=True)
        results.append(evaluate_case(f, config, out, Humanize(seed=seed)))
    (out / "results.json").write_text(json.dumps(results, indent=1))
    table = summary_table(results)
    (out / "summary.md").write_text(table + "\n")
    print(table)
    return results
