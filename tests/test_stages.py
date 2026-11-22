"""Tests for the reader, quantizer corrections, overtone filter, evals and web API."""

import json
import shutil
import urllib.error
import threading
import urllib.request
from functools import partial
from pathlib import Path

import pytest

from tabscribe.adapters.audio.folder_stems import FolderStems
from tabscribe.adapters.ml.basic_pitch import suppress_overtones
from tabscribe.adapters.notation.alphatex import AlphaTexWriter
from tabscribe.adapters.quantize.grid import GridQuantizer
from tabscribe.application import ports
from tabscribe.domain import (
    TICKS_PER_BEAT,
    AudioRef,
    ChordSegment,
    DrumHit,
    DrumPart,
    DrumPiece,
    DrumTrack,
    Harmony,
    NoteEvent,
    PitchedPart,
    PitchedTrack,
    Rhythm,
    Role,
    ScoreHit,
    ScoreNote,
    Song,
    drums,
    guitar,
)

ROOT = Path(__file__).resolve().parents[1]
HAS_ALPHATAB = bool(shutil.which("node")) and (ROOT / "node_modules/@coderline/alphatab").exists()
needs_alphatab = pytest.mark.skipif(not HAS_ALPHATAB, reason="needs node and `npm install`")


# --- reader ---------------------------------------------------------------------

@needs_alphatab
def test_reader_round_trips_every_case():
    from tabscribe.adapters.notation.alphatex_reader import AlphaTexReader
    reader, writer = AlphaTexReader(), AlphaTexWriter()
    assert isinstance(reader, ports.SongReader)
    for path in [ROOT / "examples/demo.atex", *sorted((ROOT / "evals/cases").glob("*.atex"))]:
        song = reader.read(path.read_text())
        again = reader.read(writer.write(song))
        for a, b in zip(song.parts, again.parts):
            key = (lambda n: (n.start, n.pitch, n.string, n.fret)) if isinstance(a, PitchedPart) \
                else (lambda h: (h.start, h.piece))
            items = (lambda p: p.notes) if isinstance(a, PitchedPart) else (lambda p: p.hits)
            assert sorted(map(key, items(a))) == sorted(map(key, items(b))), path.name


@needs_alphatab
def test_song_starting_with_a_chord_survives_the_tuning_line():
    """Regression: `\\tuning E4 ...` without parentheses swallowed the first beat."""
    from tabscribe.adapters.notation.alphatex_reader import AlphaTexReader
    chord = [ScoreNote(0, 48, 40, 6, 0), ScoreNote(0, 48, 47, 5, 2)]
    song = Song(parts=[PitchedPart(guitar(), chord)])
    back = AlphaTexReader().read(AlphaTexWriter().write(song))
    assert len(back.parts[0].notes) == 2


@needs_alphatab
def test_reader_reports_line_and_column():
    from tabscribe.adapters.notation.alphatex_reader import AlphaTexParseError, AlphaTexReader
    with pytest.raises(AlphaTexParseError, match="line 2"):
        AlphaTexReader().read('\\track "x"\n3.5.4 (bad |')


# --- quantizer corrections ----------------------------------------------------------

BEAT = 0.5  # 120 bpm


def grid(n, offset=0.0):
    return tuple(offset + i * BEAT for i in range(n))


def test_quantizer_keeps_pickup_notes():
    rhythm = Rhythm(120, beat_times=grid(16, 1.0), downbeat_times=grid(16, 1.0)[::4])
    track = PitchedTrack(guitar(), [NoteEvent(0.5, 0.7, 64), NoteEvent(1.0, 1.2, 65)])
    song = GridQuantizer().quantize([track], rhythm, Harmony(), "t")
    starts = [n.start for n in song.parts[0].notes]
    assert len(starts) == 2  # the pickup was not dropped
    assert starts[1] - starts[0] == TICKS_PER_BEAT and starts[1] % song.ticks_per_bar == 0


def test_quantizer_moves_bar_line_to_chord_changes():
    # Tracker says bars start on beat 3; chords change every 4 beats from 0.
    beats = grid(17)
    rhythm = Rhythm(120, beat_times=beats, downbeat_times=beats[2::4])
    harmony = Harmony(chords=tuple(ChordSegment(i * 2.0, i * 2.0 + 2.0, c)
                                   for i, c in enumerate(["C", "G", "Am", "F"])))
    track = PitchedTrack(guitar(), [NoteEvent(0.0, 0.4, 48)])
    song = GridQuantizer().quantize([track], rhythm, harmony, "t")
    assert [c.start % song.ticks_per_bar for c in song.chords] == [0, 0, 0, 0]


def test_quantizer_fixes_beats_on_the_offbeat():
    # Kick and snare on real beats (every 0.5 s); tracker reports the "and"s.
    hits = [DrumHit(i * BEAT, DrumPiece.KICK if i % 2 == 0 else DrumPiece.SNARE) for i in range(16)]
    rhythm = Rhythm(120, beat_times=grid(16, 0.25), downbeat_times=grid(16, 0.25)[::4])
    song = GridQuantizer().quantize([DrumTrack(drums(), hits)], rhythm, Harmony(), "t")
    assert all(h.start % TICKS_PER_BEAT == 0 for h in song.parts[0].hits)


def test_quantizer_leaves_good_rhythm_alone():
    hits = [DrumHit(i * BEAT, DrumPiece.KICK) for i in range(16)]
    rhythm = Rhythm(120, beat_times=grid(16), downbeat_times=grid(16)[::4])
    song = GridQuantizer().quantize([DrumTrack(drums(), hits)], rhythm, Harmony(), "t")
    assert [h.start for h in song.parts[0].hits] == [i * TICKS_PER_BEAT for i in range(16)]


# --- overtone filter --------------------------------------------------------------

def test_overtones_removed_but_real_octaves_kept():
    fundamental = NoteEvent(0.0, 1.0, 40, confidence=0.8)
    ghost_octave = NoteEvent(0.01, 0.5, 52, confidence=0.35)
    ghost_twelfth = NoteEvent(0.0, 0.5, 59, confidence=0.3)
    real_octave = NoteEvent(1.5, 2.0, 52, confidence=0.75)  # its own note later
    strummed = [NoteEvent(3.0, 4.0, 40, confidence=0.7), NoteEvent(3.01, 4.0, 52, confidence=0.68)]
    kept = suppress_overtones([fundamental, ghost_octave, ghost_twelfth, real_octave, *strummed], 0.8)
    assert ghost_octave not in kept and ghost_twelfth not in kept
    assert fundamental in kept and real_octave in kept and all(n in kept for n in strummed)


# --- folder stems ------------------------------------------------------------------

def test_folder_stems_finds_files_next_to_the_mix(tmp_path):
    (tmp_path / "song_stems").mkdir()
    (tmp_path / "song_stems" / "bass.wav").write_bytes(b"x")
    (tmp_path / "song_stems" / "drums.flac").write_bytes(b"x")
    stems = FolderStems().separate(AudioRef(tmp_path / "song.wav"),
                                   [Role.GUITAR, Role.BASS, Role.DRUMS], tmp_path)
    assert set(stems) == {Role.BASS, Role.DRUMS}
    assert isinstance(FolderStems(), ports.SourceSeparator)


# --- eval scoring ---------------------------------------------------------------------

def test_metrics_are_perfect_on_the_truth():
    pytest.importorskip("mir_eval")
    from tabscribe.evals import metrics
    from tabscribe.evals.synth import Humanize, humanize
    song = Song(tempo_bpm=100, parts=[
        PitchedPart(guitar(), [ScoreNote(i * 24, 24, 52 + i % 5, 4, 2 + i % 5) for i in range(16)]),
        DrumPart(drums(), [ScoreHit(i * 48, DrumPiece.KICK) for i in range(8)]),
    ])
    tracks, rhythm, _ = humanize(song, Humanize(seed=1))
    assert metrics.notes(tracks[0].notes, tracks[0].notes)["f1"] == 1.0
    assert metrics.drums(tracks[1].hits, tracks[1].hits)["all"]["f1"] == 1.0
    assert metrics.beats(rhythm, rhythm)["beat_f1"] == 1.0
    q = GridQuantizer().quantize(tracks, rhythm, Harmony(), "t")
    assert metrics.score_notes(song.parts[0].notes, q.parts[0].notes)["f1"] == 1.0


# --- web API ---------------------------------------------------------------------------

@pytest.fixture
def web(tmp_path):
    import http.server
    from tabscribe.web.server import App, Handler
    (tmp_path / "demo.atex").write_text((ROOT / "examples/demo.atex").read_text())
    app = App(tmp_path, ROOT / "examples/fake.toml")
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), partial(Handler, app=app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}", tmp_path
    httpd.shutdown()


def _req(url, method="GET", data=None, headers=None):
    r = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    with urllib.request.urlopen(r) as resp:
        return json.loads(resp.read())


def test_web_lists_reads_and_saves_songs(web):
    base, lib = web
    assert [s["name"] for s in _req(f"{base}/api/songs")] == ["demo"]
    song = _req(f"{base}/api/songs/demo")
    assert song["text"].startswith('\\title "Demo"')
    _req(f"{base}/api/songs/demo", "PUT", song["text"].replace("Demo", "Edited").encode())
    assert '"Edited"' in (lib / "demo.atex").read_text()


def test_web_rejects_paths_outside_the_library(web):
    base, _ = web
    with pytest.raises(urllib.error.HTTPError) as e:
        _req(f"{base}/api/songs/..%2F..%2Fetc%2Fpasswd")
    assert e.value.code in (400, 404)


def test_web_transcribes_an_upload(web):
    import time
    base, lib = web
    job = _req(f"{base}/api/transcribe", "POST", b"RIFFfake", {"X-Filename": "my%20take.wav"})["job"]
    for _ in range(50):
        status = _req(f"{base}/api/jobs/{job}")
        if status["status"] != "running":
            break
        time.sleep(0.1)
    assert status["status"] == "done", status
    assert status["done"][-1] == "Clean-up"
    assert (lib / "my take.atex").exists()


# --- recording sync and media ------------------------------------------------------------

def _fake_song():
    from tabscribe.adapters.testing.fakes import FakeHarmony, FakePitch, FakeRhythm
    mix = AudioRef(Path("x.wav"))
    rhythm = FakeRhythm().analyze(mix)
    track = PitchedTrack(guitar(), FakePitch().transcribe(mix, guitar()))
    return GridQuantizer().quantize([track], rhythm, FakeHarmony().analyze(mix, rhythm), "t"), rhythm


def test_quantizer_records_where_each_beat_is_in_the_recording():
    song, rhythm = _fake_song()
    assert [p.seconds for p in song.sync] == [round(b, 4) for b in rhythm.beat_times]
    assert [p.tick for p in song.sync] == [i * TICKS_PER_BEAT for i in range(len(rhythm.beat_times))]


@needs_alphatab
def test_sync_points_survive_writing_and_reading():
    from tabscribe.adapters.notation.alphatex_reader import AlphaTexReader
    song, _ = _fake_song()
    text = AlphaTexWriter().write(song)
    assert "\\sync (" in text
    back = AlphaTexReader().read(text)
    assert [(p.tick, round(p.seconds, 3)) for p in back.sync] == \
        [(p.tick, round(p.seconds, 3)) for p in song.sync]


def test_media_saved_and_listed_mix_first(tmp_path):
    from tabscribe.library import list_media, save_media
    mix = tmp_path / "take.mp3"
    mix.write_bytes(b"mix")
    stem = tmp_path / "g.wav"
    stem.write_bytes(b"gtr")
    save_media(tmp_path, "Song", mix, {Role.GUITAR: AudioRef(stem), Role.BASS: AudioRef(mix)})
    listed = list_media(tmp_path, "Song")
    assert [m["file"] for m in listed] == ["mix.mp3", "guitar.wav"]  # bass was the mix itself: skipped
    assert listed[0]["label"] == "Full recording"


def test_web_serves_media_with_ranges(web):
    from tabscribe.library import media_dir
    base, lib = web
    folder = media_dir(lib, "demo")
    folder.mkdir()
    (folder / "mix.wav").write_bytes(bytes(range(256)) * 4)
    assert _req(f"{base}/api/media/demo")[0]["file"] == "mix.wav"
    r = urllib.request.Request(f"{base}/media/demo/mix.wav", headers={"Range": "bytes=10-19"})
    with urllib.request.urlopen(r) as resp:
        assert resp.status == 206
        assert resp.headers["Content-Range"] == "bytes 10-19/1024"
        assert resp.read() == bytes(range(10, 20))
    assert [s["media"] for s in _req(f"{base}/api/songs")] == [True]


def test_web_transcription_keeps_the_recording(web):
    import time
    base, lib = web
    job = _req(f"{base}/api/transcribe", "POST", b"RIFFfake", {"X-Filename": "take.wav"})["job"]
    for _ in range(50):
        if _req(f"{base}/api/jobs/{job}")["status"] != "running":
            break
        time.sleep(0.1)
    assert (lib / "take.media" / "mix.wav").read_bytes() == b"RIFFfake"
