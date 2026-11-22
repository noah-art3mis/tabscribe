"""Build a small hand-made song (guitar, bass, drums) to try the edit loop
without any audio models. Run: python examples/make_demo.py"""

from pathlib import Path

from tabscribe import alphatex, ascii_tab
from tabscribe.model import Note, Song, Track

TEMPO = 100
EIGHTH = 60 / TEMPO / 2
PROGRESSION = ["C", "G", "Am", "F"]

GUITAR_SHAPES = {  # (string, fret) arpeggio per chord
    "C": [(5, 3), (4, 2), (3, 0), (2, 1)],
    "G": [(6, 3), (5, 2), (4, 0), (3, 0)],
    "Am": [(5, 0), (4, 2), (3, 2), (2, 1)],
    "F": [(4, 3), (3, 2), (2, 1), (1, 1)],
}
BASS_ROOTS = {"C": (3, 3), "G": (4, 3), "Am": (3, 0), "F": (4, 1)}  # (string, fret)

song = Song(title="Demo", tempo=TEMPO)
guitar, bass, drums = Track.guitar(), Track.bass(), Track.drums()

t = 0.0
for name in PROGRESSION:
    song.chords.append((t, t + 8 * EIGHTH, name))
    for i in range(8):
        s, f = GUITAR_SHAPES[name][i % 4]
        guitar.notes.append(Note(t, t + EIGHTH, 0, s, f))
        drums.notes.append(Note(t, t + EIGHTH, 42))  # closed hi-hat on every 8th
        if i in (0, 4):
            drums.notes.append(Note(t, t + EIGHTH, 36))  # kick on 1 and 3
        if i in (2, 6):
            drums.notes.append(Note(t, t + EIGHTH, 38))  # snare on 2 and 4
        if i % 2 == 0:
            s, f = BASS_ROOTS[name]
            bass.notes.append(Note(t, t + 2 * EIGHTH, 0, s, f))
        t += EIGHTH

song.tracks = [guitar, bass, drums]
here = Path(__file__).parent
(here / "demo.atex").write_text(alphatex.export(song))
(here / "demo.txt").write_text(ascii_tab.render(song))
print("wrote examples/demo.atex and examples/demo.txt")
