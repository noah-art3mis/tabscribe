// Parse an .atex file with alphaTab and print a per-track summary.
// Usage: node scripts/check_atex.mjs song.atex
import * as alphaTab from '@coderline/alphatab';
import fs from 'node:fs';

const file = process.argv[2];
if (!file) {
  console.error('usage: node scripts/check_atex.mjs <file.atex>');
  process.exit(2);
}

try {
  const importer = new alphaTab.importer.AlphaTexImporter();
  importer.initFromString(fs.readFileSync(file, 'utf8'), new alphaTab.Settings());
  const score = importer.readScore();
  console.log(`OK: "${score.title}" at ${score.tempo} bpm`);
  for (const track of score.tracks) {
    const staff = track.staves[0];
    const notes = staff.bars
      .flatMap(bar => bar.voices.flatMap(v => v.beats))
      .reduce((sum, beat) => sum + beat.notes.length, 0);
    console.log(`  ${track.name}: ${staff.bars.length} bars, ${notes} notes`);
  }
} catch (err) {
  console.error(`ERROR in ${file}:\n${err.message}`);
  process.exit(1);
}
