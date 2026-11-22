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
  };

  const TRACK_COLORS = ['#e8743b', '#4f9fe8', '#5cb85c', '#c678dd', '#e5c07b', '#56b6c2'];
  const ZOOMS = [0.5, 0.6, 0.75, 0.9, 1, 1.1, 1.25, 1.5, 1.75, 2];
  const JOB_STAGES = ['Beats and bars', 'Chords', 'Separate and transcribe', 'Snap to grid',
                      'Strings and frets', 'Clean-up'];

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
    buildTrackList(score);
  });
  api.midiLoaded.on(() => applyMixer());
  api.playerReady.on(() => {
    state.playerReady = true;
    el.play.disabled = el.stop.disabled = false;
  });
  api.playerStateChanged.on((e) => {
    el.play.classList.toggle('playing', e.state === 1);
    el.play.title = e.state === 1 ? 'Pause (Space)' : 'Play (Space)';
  });
  api.playerPositionChanged.on((e) => {
    el.time.textContent = `${fmtTime(e.currentTime)} / ${fmtTime(e.endTime)}`;
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
  el.stop.addEventListener('click', () => api.stop());
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
