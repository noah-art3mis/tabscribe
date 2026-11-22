// Parse alphaTex with alphaTab and print the song as JSON on stdout.
// Used by tabscribe's AlphaTexReader. Usage: node scripts/atex_to_json.mjs < song.atex
// Times are alphaTab MIDI ticks (960 per quarter note); strings use
// alphaTab's numbering (1 = lowest). The Python side converts both.
import * as alphaTab from '@coderline/alphatab';
import fs from 'node:fs';

const tex = fs.readFileSync(0, 'utf8');
let score;
try {
  const importer = new alphaTab.importer.AlphaTexImporter();
  importer.initFromString(tex, new alphaTab.Settings());
  score = importer.readScore();
} catch (err) {
  const inner = err.cause ?? err.inner ?? err;
  const items = ['lexerDiagnostics', 'parserDiagnostics', 'semanticDiagnostics']
    .flatMap(k => inner?.[k]?.items ?? [])
    .filter(d => d.severity === 2)
    .map(d => ({ line: d.start?.line, col: d.start?.col, message: d.message }));
  process.stdout.write(JSON.stringify({ error: err.message, diagnostics: items }));
  process.exit(1);
}

const effects = n => {
  const fx = [];
  if (n.isHammerPullOrigin) fx.push('h');
  if (n.slideOutType) fx.push('sl');
  if (n.isPalmMute) fx.push('pm');
  if (n.isDead) fx.push('x');
  if (n.vibrato) fx.push('v');
  if (n.isLetRing) fx.push('lr');
  if (n.hasBend) fx.push('b (' + n.bendPoints.map(p => p.value).join(' ') + ')');
  return fx;
};

const bar0 = score.masterBars[0];
const sync = (score.exportFlatSyncPoints?.() ?? [])
  .filter(p => p.barIndex < score.masterBars.length && p.barOccurence === 0)
  .map(p => {
    const mb = score.masterBars[p.barIndex];
    return { tick: mb.start + p.barPosition * mb.calculateDuration(), ms: p.millisecondOffset };
  });
const out = {
  sync,
  title: score.title,
  tempo: score.tempo,
  beatsPerBar: bar0.timeSignatureNumerator,
  beatUnit: bar0.timeSignatureDenominator,
  tracks: score.tracks.map(track => {
    const staff = track.staves[0];
    const chordNames = new Map([...(staff.chords?.entries?.() ?? [])].map(([id, c]) => [id, c.name]));
    const events = [];
    const chords = [];
    for (const bar of staff.bars) {
      for (const voice of bar.voices) {
        for (const beat of voice.beats) {
          if (beat.chordId && chordNames.has(beat.chordId)) {
            chords.push({ start: beat.absolutePlaybackStart, label: chordNames.get(beat.chordId) });
          }
          for (const n of beat.notes) {
            const base = { start: beat.absolutePlaybackStart, duration: beat.playbackDuration };
            if (track.isPercussion) {
              const art = track.percussionArticulations[n.percussionArticulation];
              events.push({ ...base, drum: art ? art.outputMidiNumber : null });
            } else {
              events.push({ ...base, pitch: n.realValue, string: n.string, fret: n.fret, effects: effects(n) });
            }
          }
        }
      }
    }
    return {
      name: track.name,
      percussion: track.isPercussion,
      program: track.playbackInfo.program,
      tuning: track.isPercussion ? [] : Array.from(staff.tuning),
      events,
      chords,
    };
  }),
};
process.stdout.write(JSON.stringify(out));
