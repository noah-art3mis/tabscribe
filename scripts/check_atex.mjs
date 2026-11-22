// Parse an .atex file with alphaTab and print a per-track summary.
// Usage: node scripts/check_atex.mjs song.atex
// Exits 1 on errors. Warnings (e.g. outdated syntax) are listed but don't fail.
import * as alphaTab from '@coderline/alphatab';
import fs from 'node:fs';

const file = process.argv[2];
if (!file) {
  console.error('usage: node scripts/check_atex.mjs <file.atex>');
  process.exit(2);
}

const LEVEL = { 0: 'hint', 1: 'warning', 2: 'error' };
const importer = new alphaTab.importer.AlphaTexImporter();
importer.initFromString(fs.readFileSync(file, 'utf8'), new alphaTab.Settings());

let score = null;
let failure = null;
try {
  score = importer.readScore();
} catch (err) {
  failure = err;
}

const source = failure?.cause ?? failure?.inner ?? importer;
const diagnostics = ['lexerDiagnostics', 'parserDiagnostics', 'semanticDiagnostics']
  .flatMap(k => source?.[k]?.items ?? importer[k]?.items ?? []);
const report = d => `  line ${d.start?.line ?? '?'}, col ${d.start?.col ?? '?'}: ${LEVEL[d.severity] ?? 'note'}: ${d.message}`;

if (failure) {
  console.error(`ERROR in ${file}`);
  const errors = diagnostics.filter(d => d.severity === 2);
  for (const d of (errors.length ? errors : diagnostics)) console.error(report(d));
  if (!diagnostics.length) console.error(`  ${failure.message}`);
  process.exit(1);
}

console.log(`OK: "${score.title}" at ${score.tempo} bpm`);
for (const track of score.tracks) {
  const staff = track.staves[0];
  const notes = staff.bars
    .flatMap(bar => bar.voices.flatMap(v => v.beats))
    .reduce((sum, beat) => sum + beat.notes.length, 0);
  console.log(`  ${track.name}: ${staff.bars.length} bars, ${notes} notes`);
}
const warnings = diagnostics.filter(d => d.severity === 1);
if (warnings.length) {
  console.log(`${warnings.length} warning(s):`);
  for (const d of warnings.slice(0, 10)) console.log(report(d));
}
