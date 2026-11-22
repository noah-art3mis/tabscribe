/* tabscribe web app: library, alphaTab score view and player, alphaTex editor,
   and transcription jobs. Talks to the local server in tabscribe/web/server.py. */
(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const el = {
    body: document.body,
    score: $('score'), scoreWrap: $('scoreWrap'), songTitle: $('songTitle'),
    songs: $('songs'), tracks: $('tracks'), jobs: $('jobs'), audioInput: $('audioInput'),
    play: $('btnPlay'), stop: $('btnStop'), time: $('time'), speed: $('speed'),
    loop: $('btnLoop'), metronome: $('btnMetronome'), countIn: $('btnCountIn'),
    notation: $('btnNotation'), layout: $('btnLayout'),
    zoomIn: $('zoomIn'), zoomOut: $('zoomOut'), zoomLabel: $('zoomLabel'),
    sourceBtn: $('btnSource'), sourcePanel: $('sourcePanel'), editor: $('editor'), gutter: $('gutter'),
    save: $('btnSave'), revert: $('btnRevert'), sourceState: $('sourceState'), sourceError: $('sourceError'),
    diskBanner: $('diskBanner'), loadDisk: $('btnLoadDisk'), keepMine: $('btnKeepMine'),
    status: $('status'), pipelineInfo: $('pipelineInfo'),
    recPanel: $('recordingPanel'), recSource: $('recSource'), mix: $('mix'), ab: $('btnAB'),
    split: $('btnSplit'), swap: $('btnSwap'), splitLabel: $('splitLabel'), offset: $('offset'),
    hearing: $('hearing'), audio: $('recording'),
  };

  const TRACK_COLORS = ['#e8743b', '#4f9fe8', '#5cb85c', '#c678dd', '#e5c07b', '#56b6c2'];
  const ZOOMS = [0.5, 0.6, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];
  const JOB_STAGES = ['Beats and bars', 'Chords', 'Separate instruments', 'Notes and drums',
                      'Snap to grid', 'Strings and frets', 'Clean-up'];

  const state = {
    name: null,          // open song (file name without .atex)
    savedText: '',       // text as last saved / loaded from disk
    mtime: 0,
    dirty: false,
    score: null,
    hidden: new Set(),   // track names hidden from the score view
    mute: new Set(),
    solo: new Set(),
    volume: new Map(),
    zoom: 1,
    notation: false,
    playerReady: false,
  };

  // Recording-vs-tab playback state (see the "recording vs tab" section below).
  const ALPHATAB_TICKS = 960;  // per quarter note
  const rec = {
    sources: [], anchors: [], playing: false,
    ctx: null, node: null, gain: null, pan: null,
    mix: 0.5, lastMix: 0.5, split: false, swapped: false, offsetMs: 0,
  };

  // ---- alphaTab ---------------------------------------------------------------

  const api = new alphaTab.AlphaTabApi(el.score, {
    core: { fontDirectory: '/alphatab/font/' },
    display: { scale: state.zoom, layoutMode: alphaTab.LayoutMode.Page },
    player: {
      enablePlayer: true,
      enableCursor: true,
      enableUserInteraction: true,
      soundFont: '/alphatab/soundfont/sonivox.sf2',
      scrollElement: el.scoreWrap,
    },
  });

  function describeError(e) {
    const inner = (e && (e.cause || e.inner)) || e;
    const all = ['lexerDiagnostics', 'parserDiagnostics', 'semanticDiagnostics']
      .flatMap((k) => (inner && inner[k] && inner[k].items) || []);
    const errors = all.filter((d) => d.severity === 2);  // 1 = warning, 0 = hint
    const items = errors.length ? errors : all;
    if (items.length) {
      return items.map((d) => `line ${d.start ? d.start.line : '?'}, col ${d.start ? d.start.col : '?'}: ${d.message}`).join('\n');
    }
    return (e && e.message) || String(e);
  }

  api.error.on((e) => showSourceError(describeError(e)));
  api.renderStarted.on(() => setStatus('Rendering…'));
  api.renderFinished.on(() => setStatus(state.name ? `${state.name}.atex` : 'Ready'));

  api.scoreLoaded.on((score) => {
    state.score = score;
    applyNotation(score);
    applyBalance(score);
    buildTrackList(score);
    rec.anchors = syncAnchors(score);
  });
  api.midiLoaded.on(() => applyMixer());
  api.playerReady.on(() => {
    state.playerReady = true;
    el.play.disabled = el.stop.disabled = false;
  });
  api.playerStateChanged.on((e) => {
    el.play.classList.toggle('playing', e.state === 1);
    el.play.title = e.state === 1 ? 'Pause (Space)' : 'Play (Space)';
    recOnPlayerState(e.state === 1);
  });
  api.playerPositionChanged.on((e) => {
    el.time.textContent = `${fmtTime(e.currentTime)} / ${fmtTime(e.endTime)}`;
    recFollow(e.currentTick);
  });

  function fmtTime(ms) {
    const s = Math.max(0, Math.floor(ms / 1000));
    return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
  }

  function renderText(text) {
    hideSourceError();
    const count = (text.match(/\\track\b/g) || []).length || 1;
    try {
      api.tex(text, [...Array(count).keys()]);
    } catch (e) {
      showSourceError(describeError(e));
    }
  }

  function visibleTracks(score) {
    const shown = score.tracks.filter((t) => !state.hidden.has(t.name));
    return shown.length ? shown : score.tracks;
  }

  function applyNotation(score) {
    for (const track of score.tracks) {
      for (const staff of track.staves) {
        if (!track.isPercussion) {
          staff.showTablature = true;
          staff.showStandardNotation = state.notation;
        }
      }
    }
  }

  function applyMixer() {
    if (!state.score) return;
    for (const t of state.score.tracks) {
      api.changeTrackMute([t], state.mute.has(t.name));
      api.changeTrackSolo([t], state.solo.has(t.name));
      api.changeTrackVolume([t], state.volume.has(t.name) ? state.volume.get(t.name) : 1);
    }
  }

  // ---- tracks panel --------------------------------------------------------------

  function buildTrackList(score) {
    el.tracks.innerHTML = '';
    score.tracks.forEach((track, i) => {
      const li = document.createElement('li');
      const color = TRACK_COLORS[i % TRACK_COLORS.length];
      const kind = track.isPercussion ? 'Drums' : `${track.staves[0].tuning.length}-string`;
      li.innerHTML = `
        <span class="dot" style="background:${color}"></span>
        <span class="name" title="Show / hide in the score"></span>
        <span class="ms">
          <button class="mute" title="Mute" aria-pressed="false">M</button>
          <button class="solo" title="Solo" aria-pressed="false">S</button>
        </span>
        <span class="muted" style="font-size:12px">${kind}</span>
        <input type="range" min="0" max="2" step="0.05" title="Volume" aria-label="${track.name} volume">`;
      const name = li.querySelector('.name');
      name.textContent = track.name;
      name.classList.toggle('hidden-track', state.hidden.has(track.name));
      name.addEventListener('click', () => {
        if (state.hidden.has(track.name)) state.hidden.delete(track.name);
        else if (score.tracks.length - state.hidden.size > 1) state.hidden.add(track.name);
        name.classList.toggle('hidden-track', state.hidden.has(track.name));
        api.renderTracks(visibleTracks(score));
      });
      const mute = li.querySelector('.mute');
      const solo = li.querySelector('.solo');
      mute.setAttribute('aria-pressed', state.mute.has(track.name));
      solo.setAttribute('aria-pressed', state.solo.has(track.name));
      mute.addEventListener('click', () => toggleSet(state.mute, track.name, mute, (on) => api.changeTrackMute([track], on)));
      solo.addEventListener('click', () => toggleSet(state.solo, track.name, solo, (on) => api.changeTrackSolo([track], on)));
      const vol = li.querySelector('input');
      vol.value = state.volume.has(track.name) ? state.volume.get(track.name) : 1;
      vol.addEventListener('input', () => {
        state.volume.set(track.name, Number(vol.value));
        api.changeTrackVolume([track], Number(vol.value));
      });
      el.tracks.appendChild(li);
    });
    if (state.hidden.size) api.renderTracks(visibleTracks(score));
  }

  function toggleSet(set, key, button, apply) {
    const on = !set.has(key);
    if (on) set.add(key); else set.delete(key);
    button.setAttribute('aria-pressed', on);
    apply(on);
  }

  // ---- library ---------------------------------------------------------------------

  async function refreshLibrary() {
    let songs;
    try {
      songs = await (await fetch('/api/songs')).json();
    } catch { return; }
    el.songs.innerHTML = '';
    if (!songs.length) {
      el.songs.innerHTML = '<li class="empty">No songs yet. Transcribe a recording to start.</li>';
      return;
    }
    for (const s of songs) {
      const li = document.createElement('li');
      li.classList.toggle('active', s.name === state.name);
      const t = document.createElement('span'); t.className = 't'; t.textContent = s.title;
      const sub = document.createElement('span'); sub.className = 'sub';
      sub.textContent = `${s.name}.atex · ${s.tracks.join(', ') || 'no tracks'}`;
      if (s.media) { const dot = document.createElement('span'); dot.className = 'rec-dot'; dot.textContent = ' · ♪ recording'; sub.appendChild(dot); }
      li.append(t, sub);
      li.addEventListener('click', () => openSong(s.name));
      el.songs.appendChild(li);
    }
  }

  async function openSong(name) {
    if (state.dirty && name !== state.name && !confirm('Discard unsaved edits?')) return;
    const res = await fetch(`/api/songs/${encodeURIComponent(name)}`);
    if (!res.ok) { setStatus(`Could not open ${name}`); return; }
    const data = await res.json();
    if (name !== state.name) {
      state.hidden.clear(); state.mute.clear(); state.solo.clear(); state.volume.clear();
      api.stop();
    }
    state.name = data.name;
    state.savedText = data.text;
    state.mtime = data.mtime;
    setEditor(data.text);
    setDirty(false);
    el.diskBanner.hidden = true;
    el.body.classList.remove('no-song');
    el.songTitle.textContent = (data.text.match(/\\title\s+"([^"]*)"/) || [])[1] || data.name;
    history.replaceState(null, '', `#song=${encodeURIComponent(name)}`);
    renderText(data.text);
    refreshLibrary();
    if (data.name !== rec.loadedFor) { rec.loadedFor = data.name; loadRecording(data.name); }
  }

  // Edits made outside the app (for example by Claude Code) show up here.
  async function watchDisk() {
    if (state.name) {
      try {
        const res = await fetch(`/api/songs/${encodeURIComponent(state.name)}`);
        if (res.ok) {
          const data = await res.json();
          if (data.mtime !== state.mtime && data.text !== state.savedText) {
            state.mtime = data.mtime;
            if (state.dirty) {
              state.pendingDisk = data.text;
              el.diskBanner.hidden = false;
            } else {
              state.savedText = data.text;
              setEditor(data.text);
              renderText(data.text);
              flash('Updated from disk');
            }
          } else {
            state.mtime = data.mtime;
          }
        }
      } catch { /* server restarting */ }
    }
    setTimeout(watchDisk, 1000);
  }

  // ---- source editor --------------------------------------------------------------

  function setEditor(text) {
    el.editor.value = text;
    updateGutter();
  }

  function updateGutter() {
    const lines = el.editor.value.split('\n').length;
    el.gutter.textContent = Array.from({ length: lines }, (_, i) => i + 1).join('\n');
    el.editor.style.height = 'auto';
    el.editor.style.height = `${el.editor.scrollHeight}px`;
  }

  function setDirty(dirty) {
    state.dirty = dirty;
    el.sourceState.textContent = dirty ? 'Unsaved' : 'Saved';
    el.sourceState.classList.toggle('dirty', dirty);
    el.save.disabled = el.revert.disabled = !dirty;
  }

  let previewTimer = null;
  el.editor.addEventListener('input', () => {
    updateGutter();
    setDirty(el.editor.value !== state.savedText);
    clearTimeout(previewTimer);
    previewTimer = setTimeout(() => renderText(el.editor.value), 500);
  });
  el.editor.addEventListener('keydown', (e) => {
    if (e.key === 'Tab') {
      e.preventDefault();
      document.execCommand('insertText', false, '  ');
    }
  });

  async function save() {
    if (!state.name || !state.dirty) return;
    const text = el.editor.value;
    const res = await fetch(`/api/songs/${encodeURIComponent(state.name)}`, { method: 'PUT', body: text });
    if (!res.ok) { setStatus('Save failed'); return; }
    const data = await res.json();
    state.savedText = text;
    state.mtime = data.mtime;
    setDirty(false);
    el.diskBanner.hidden = true;
    flash('Saved');
  }

  el.save.addEventListener('click', save);
  el.revert.addEventListener('click', () => {
    setEditor(state.savedText); setDirty(false); renderText(state.savedText);
  });
  el.loadDisk.addEventListener('click', () => {
    state.savedText = state.pendingDisk;
    setEditor(state.savedText); setDirty(false); renderText(state.savedText);
    el.diskBanner.hidden = true;
  });
  el.keepMine.addEventListener('click', () => { el.diskBanner.hidden = true; });

  function showSourceError(msg) {
    el.sourceError.textContent = msg;
    el.sourceError.hidden = false;
    setStatus('alphaTex error: open Source to see where');
  }
  function hideSourceError() { el.sourceError.hidden = true; }

  // ---- toolbar ----------------------------------------------------------------------

  function pressed(button, on) { button.setAttribute('aria-pressed', String(on)); }
  [el.loop, el.metronome, el.countIn, el.notation, el.layout, el.sourceBtn].forEach((b) => pressed(b, false));

  el.play.addEventListener('click', () => api.playPause());
  el.stop.addEventListener('click', () => { api.stop(); el.audio.pause(); el.audio.currentTime = 0; });
  el.speed.addEventListener('change', () => { api.playbackSpeed = Number(el.speed.value); });
  el.loop.addEventListener('click', () => {
    api.isLooping = !api.isLooping; pressed(el.loop, api.isLooping);
  });
  el.metronome.addEventListener('click', () => {
    const on = api.metronomeVolume === 0; api.metronomeVolume = on ? 1 : 0; pressed(el.metronome, on);
  });
  el.countIn.addEventListener('click', () => {
    const on = api.countInVolume === 0; api.countInVolume = on ? 1 : 0; pressed(el.countIn, on);
  });
  api.metronomeVolume = 0;
  api.countInVolume = 0;

  el.notation.addEventListener('click', () => {
    state.notation = !state.notation;
    pressed(el.notation, state.notation);
    if (state.score) { applyNotation(state.score); api.render(); }
  });
  el.layout.addEventListener('click', () => {
    const horizontal = api.settings.display.layoutMode !== alphaTab.LayoutMode.Horizontal;
    api.settings.display.layoutMode = horizontal ? alphaTab.LayoutMode.Horizontal : alphaTab.LayoutMode.Page;
    el.body.classList.toggle('horizontal', horizontal);
    pressed(el.layout, horizontal);
    api.updateSettings(); api.render();
  });
  function setZoom(z) {
    state.zoom = z;
    el.zoomLabel.textContent = `${Math.round(z * 100)}%`;
    api.settings.display.scale = z;
    api.updateSettings(); api.render();
  }
  el.zoomIn.addEventListener('click', () => setZoom(ZOOMS[Math.min(ZOOMS.indexOf(state.zoom) + 1, ZOOMS.length - 1)]));
  el.zoomOut.addEventListener('click', () => setZoom(ZOOMS[Math.max(ZOOMS.indexOf(state.zoom) - 1, 0)]));
  el.sourceBtn.addEventListener('click', () => {
    el.sourcePanel.hidden = !el.sourcePanel.hidden;
    pressed(el.sourceBtn, !el.sourcePanel.hidden);
    updateGutter();
  });

  document.addEventListener('keydown', (e) => {
    const typing = e.target === el.editor || e.target.tagName === 'INPUT' || e.target.tagName === 'SELECT';
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 's') { e.preventDefault(); save(); return; }
    if (typing) return;
    if (e.code === 'Space' && state.playerReady) { e.preventDefault(); api.playPause(); }
    if (e.key === 'Home' && state.playerReady) { e.preventDefault(); api.stop(); }
    if (e.key.toLowerCase() === 'b') { e.preventDefault(); flipAB(); }
  });

  // ---- transcription jobs -------------------------------------------------------------

  el.audioInput.addEventListener('change', async () => {
    const file = el.audioInput.files[0];
    el.audioInput.value = '';
    if (!file) return;
    const card = document.createElement('div');
    card.className = 'job';
    card.innerHTML = '<div class="name"></div><ol></ol><div class="err" hidden></div>';
    card.querySelector('.name').textContent = file.name;
    el.jobs.prepend(card);
    drawJob(card, { status: 'uploading', done: [], stage: 'Uploading' });
    let res;
    try {
      res = await fetch('/api/transcribe', {
        method: 'POST', body: file,
        headers: { 'X-Filename': encodeURIComponent(file.name) },
      });
    } catch (e) {
      drawJob(card, { status: 'error', done: [], error: 'Upload failed' });
      return;
    }
    const { job } = await res.json();
    pollJob(job, card);
  });

  function drawJob(card, job) {
    const ol = card.querySelector('ol');
    ol.innerHTML = '';
    for (const label of JOB_STAGES) {
      const li = document.createElement('li');
      li.textContent = label;
      if (job.done.includes(label)) li.className = 'done';
      else if (job.status === 'running' && label === job.stage) li.className = 'now';
      ol.appendChild(li);
    }
    const err = card.querySelector('.err');
    err.hidden = !job.error;
    err.textContent = job.error || '';
  }

  async function pollJob(id, card) {
    let job;
    try { job = await (await fetch(`/api/jobs/${id}`)).json(); } catch { setTimeout(() => pollJob(id, card), 1500); return; }
    drawJob(card, job);
    if (job.status === 'running') { setTimeout(() => pollJob(id, card), 700); return; }
    if (job.status === 'done') {
      setTimeout(() => card.remove(), 4000);
      await refreshLibrary();
      openSong(job.song);
    }
  }


  // ---- recording vs tab --------------------------------------------------------------
  // alphaTab can't mix its synth with a backing track, so the recording plays in
  // an <audio> element routed through Web Audio (for gain and panning) and follows
  // the alphaTab cursor. The sync points in the .atex file say where each beat of
  // the score is in the recording; between them, time is interpolated.


  function syncAnchors(score) {
    const points = [];
    for (const mb of score.masterBars) {
      for (const p of mb.syncPoints || []) {
        if (p.syncPointValue.barOccurence !== 0) continue;
        points.push([mb.start + p.ratioPosition * mb.calculateDuration(), p.syncPointValue.millisecondOffset]);
      }
    }
    points.sort((a, b) => a[0] - b[0]);
    return points;
  }

  // Score position (alphaTab ticks) -> recording time (ms), plus how many recording
  // ms pass per synth ms here (the local tempo ratio).
  function recTime(tick) {
    const synthMsPerTick = 60000 / ((state.score ? state.score.tempo : 120) * ALPHATAB_TICKS);
    const a = rec.anchors;
    if (a.length < 2) return { ms: tick * synthMsPerTick, ratio: 1 };
    let i = 0;
    while (i < a.length - 2 && a[i + 1][0] <= tick) i++;
    const [t0, m0] = a[i], [t1, m1] = a[i + 1];
    const msPerTick = (m1 - m0) / Math.max(t1 - t0, 1);
    return { ms: m0 + (tick - t0) * msPerTick, ratio: msPerTick / synthMsPerTick };
  }

  function ensureGraph() {
    if (rec.ctx) return;
    rec.ctx = new (window.AudioContext || window.webkitAudioContext)();
    rec.node = rec.ctx.createMediaElementSource(el.audio);
    rec.pan = rec.ctx.createStereoPanner();
    rec.gain = rec.ctx.createGain();
    rec.node.connect(rec.pan).connect(rec.gain).connect(rec.ctx.destination);
    applyMix();
  }

  function recActive() { return rec.sources.length > 0 && el.audio.src; }

  function recOnPlayerState(playing) {
    rec.playing = playing;
    if (!recActive()) return;
    if (playing) {
      ensureGraph();
      rec.ctx.resume();
      el.audio.preservesPitch = true;
      el.audio.play().catch(() => setStatus('Click play again to start the recording'));
    } else {
      el.audio.pause();
    }
  }

  function recFollow(tick) {
    if (!recActive() || !rec.playing || tick === undefined) return;
    const { ms, ratio } = recTime(tick);
    const target = (ms + rec.offsetMs) / 1000;
    if (target < 0) { if (!el.audio.paused) el.audio.pause(); return; }
    if (el.audio.paused) el.audio.play().catch(() => {});
    const error = target - el.audio.currentTime;  // > 0: recording is behind
    const speed = api.playbackSpeed || 1;
    if (Math.abs(error) > 0.25 || !isFinite(error)) {
      el.audio.currentTime = target;
      el.audio.playbackRate = speed * ratio;
    } else {
      // follow the local tempo, and gently close any remaining gap
      const nudge = Math.max(-0.08, Math.min(0.08, error * 0.8));
      el.audio.playbackRate = Math.max(0.25, speed * ratio * (1 + nudge));
    }
  }

  function applyMix() {
    const x = rec.mix;
    const tab = Math.cos(x * Math.PI / 2), recording = Math.sin(x * Math.PI / 2);  // equal power
    api.masterVolume = recActive() ? tab : 1;
    if (rec.gain) rec.gain.gain.value = recording;
    if (rec.pan) rec.pan.pan.value = rec.split ? (rec.swapped ? -1 : 1) : 0;
    el.mix.value = x;
    el.hearing.textContent = !recActive() ? '' : x <= 0.02 ? 'Hearing the tab' : x >= 0.98 ? 'Hearing the recording' : 'Hearing both';
    el.splitLabel.hidden = !rec.split;
    el.splitLabel.textContent = rec.swapped ? 'Recording left · Tab right' : 'Tab left · Recording right';
  }

  // Pan the synthesized tab to the opposite side of the recording (MIDI balance 0-16).
  function applyBalance(score) {
    const balance = !rec.split ? 8 : rec.swapped ? 16 : 0;
    let changed = false;
    for (const t of score.tracks) {
      if (t.playbackInfo.balance !== balance) { t.playbackInfo.balance = balance; changed = true; }
    }
    return changed;
  }

  function setSplit(split, swapped) {
    rec.split = split; rec.swapped = swapped;
    pressed(el.split, split);
    el.swap.disabled = !split;
    if (state.score && applyBalance(state.score)) {
      const wasPlaying = rec.playing;
      api.loadMidiForScore();
      if (wasPlaying) setTimeout(() => api.play(), 150);
    }
    applyMix();
  }

  async function loadRecording(name) {
    rec.sources = [];
    el.audio.removeAttribute('src');
    el.audio.load();
    try {
      rec.sources = await (await fetch(`/api/media/${encodeURIComponent(name)}`)).json();
    } catch { rec.sources = []; }
    el.recPanel.hidden = rec.sources.length === 0;
    el.recSource.innerHTML = '';
    for (const s of rec.sources) {
      const o = document.createElement('option');
      o.value = s.file; o.textContent = s.label;
      el.recSource.appendChild(o);
    }
    if (rec.sources.length) setRecSource(rec.sources[0].file);
    applyMix();
  }

  function setRecSource(file) {
    const t = el.audio.currentTime;
    el.audio.src = `/media/${encodeURIComponent(state.name)}/${encodeURIComponent(file)}`;
    el.audio.currentTime = t || 0;
    if (rec.playing) el.audio.play().catch(() => {});
  }

  function flipAB() {
    if (!recActive()) return;
    if (rec.mix > 0.02 && rec.mix < 0.98) rec.lastMix = rec.mix;
    rec.mix = rec.mix >= 0.5 ? 0 : 1;
    applyMix();
  }

  el.recSource.addEventListener('change', () => setRecSource(el.recSource.value));
  el.mix.addEventListener('input', () => { rec.mix = Number(el.mix.value); applyMix(); });
  el.ab.addEventListener('click', flipAB);
  el.split.addEventListener('click', () => setSplit(!rec.split, rec.swapped));
  el.swap.addEventListener('click', () => setSplit(rec.split, !rec.swapped));
  el.offset.addEventListener('change', () => { rec.offsetMs = Number(el.offset.value) || 0; });
  pressed(el.split, false);

  // ---- status ---------------------------------------------------------------------------

  function setStatus(msg) { el.status.textContent = msg; }
  let flashTimer = null;
  function flash(msg) {
    setStatus(msg);
    clearTimeout(flashTimer);
    flashTimer = setTimeout(() => setStatus(state.name ? `${state.name}.atex` : 'Ready'), 2000);
  }

  async function showPipeline() {
    try {
      const info = await (await fetch('/api/pipeline')).json();
      const s = info.stages;
      const parts = s.mix_transcriber ? [`end-to-end: ${s.mix_transcriber}`]
        : [s.separator, s.pitch, s.drums].filter(Boolean);
      el.pipelineInfo.textContent = `Pipeline: ${[...parts, s.rhythm, s.fretter].filter(Boolean).join(' · ')}`;
    } catch { /* ignore */ }
  }

  // ---- start ----------------------------------------------------------------------------

  window.tabscribe = { api, rec, state };  // for debugging in the browser console
  el.body.classList.add('no-song');
  refreshLibrary();
  setInterval(refreshLibrary, 4000);
  showPipeline();
  watchDisk();
  const songFromHash = () => new URLSearchParams(location.hash.slice(1)).get('song');
  window.addEventListener('hashchange', () => {
    const name = songFromHash();
    if (name && name !== state.name) openSong(name);
  });
  if (songFromHash()) openSong(songFromHash());
})();
