# tabscribe design

This file owns tabscribe's visual identity: the web app in `src/tabscribe/web/static/`. Read it before changing any of it. A design skill supplies craft inside this direction; changing the direction is the owner's call, recorded here once accepted.

## Context

- **Users** – the owner and other musicians cleaning up a transcription: listening, comparing with the recording, fixing tabs by prompting Claude Code.
- **Scale** – a local, single-user app on `localhost`.
- **Devices** – desktop; narrow screens only need to stay usable.
- **Environment** – long practice sessions, often with an instrument in hand: controls must read at a glance and work from the keyboard.
- **Language** – English, sentence case, musician's vocabulary (track, bar, mute, solo, count-in).
- **Priorities** – the score first; speed of iteration over polish (it is an open prototype).
- **Out of scope** – marketing pages, accounts, mobile optimisation.

## Overview

**Console tape.** The app is a small mixing desk with the score as its paper. Flat blue-grey panels, one amber lamp colour for whatever is on or playing, and the single textured element: strips of console tape with names in marker, the way every rehearsal-room desk is labelled. Spend boldness on the tape and keep everything else quiet.

## Brand

The wordmark is "tabscribe" written in marker on a strip of masking tape (`.brand.tape`). No logo file. Voice: plain and practical, like a label on gear.

## Tokens

All values live at the top of `src/tabscribe/web/static/app.css`; rules use the variables, and tints are `color-mix()` on a token.

- **Colour** – `--ground` behind the score, `--panel`/`--panel-2` for chrome, `--recess` for inset displays (time counter, editor, active song). `--amber` is the lamp: play, playhead, lit toggles, solo, the primary button; `--amber-text` is its text form. `--mute` only for mute and errors. `--paper` is the score. Six tape colours (`--tape-*`) are assigned to tracks in order.
- **Type** – Barlow Semi Condensed (hardware-legend signage) for all UI, 15px base, sentence-case headings at 16px/600. Permanent Marker only on tape. The system monospace only in the alphaTex editor. Times and numbers use tabular figures.
- **Radius** – 6px on controls, round only for the play button, none on tape.
- **Elevation** – none: levels come from panel vs recess vs ground.
- **Motion** – colour transitions at `--t-fast` with `--ease-out`; nothing moves position. Off under reduced motion.

## Components

| Pattern           | Owner                         | Notes                                                       |
|-------------------|-------------------------------|-------------------------------------------------------------|
| Tape label        | `.tape` in `app.css`          | Brand and track names; slight rotation, torn ends; colour from `--tape` |
| Button            | `button`, `.button.primary`   | One primary per surface (Transcribe audio…, Save)           |
| Toggle            | `.toggle` + `aria-pressed`    | Lamp dot before the label lights amber when on              |
| Channel strip     | `.tracks li` (built in `app.js` `buildTrackList`) | Tape name (click hides the track), M/S, kind, fader |
| Fader             | `input[type=range]`           | Recessed track, flat cap with a centre line                 |
| Job progress      | `.job` (built in `app.js`)    | The pulsing dot marks only the running stage                |

## Things to avoid

- More texture: no brushed metal, knobs, wood or shadows. The tape is the only skeuomorphic element.
- A second accent colour, or amber on things that are not on, playing or primary.
- Uppercase tracked labels and one-word accents in headings.
