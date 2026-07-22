/* ── State ──────────────────────────────────────────────────────────── */
const API = '';
let currentVid    = '';
let currentArtist = '';
let currentTitle  = '';
let lastStatus    = {};
let seekDragging  = false;
let pollTimer     = null;
let suggTimer     = null;
let searchResults = [];
let localLibrary  = [];
let history       = JSON.parse(localStorage.getItem('ttube_history') || '[]');
let plModalVid    = '';
let plModalUrl    = '';
let plModalTitle  = '';
let allPlaylists  = [];

/* ── Utilities ──────────────────────────────────────────────────────── */
const $  = id => document.getElementById(id);
const q  = sel => document.querySelector(sel);
const qq = sel => document.querySelectorAll(sel);
const show   = el => el && el.classList.remove('hidden');
const hide   = el => el && el.classList.add('hidden');
const toggle = (el, on) => on ? show(el) : hide(el);
const fmt = s => {
  if (s == null) return '--:--';
  const t = Math.max(0, Math.floor(s));
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), sec = t % 60;
  return h ? `${h}:${m.toString().padStart(2,'0')}:${sec.toString().padStart(2,'0')}` : `${m}:${sec.toString().padStart(2,'0')}`;
};
function escHtml(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
}
function encodeArt(url) {
  return `/api/artwork?url=${encodeURIComponent(url)}`;
}

/* ── Init & Views ───────────────────────────────────────────────────── */
function setGreeting() {
  const h = new Date().getHours();
  $('main-title').textContent = h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
}

function switchView(viewName) {
  qq('.view-panel').forEach(p => p.classList.remove('active'));
  qq('.nav-btn').forEach(b => b.classList.toggle('active', b.dataset.view === viewName));
  const p = $(`view-${viewName}`);
  if (p) p.classList.add('active');

  $('scroll-wrap').scrollTo(0,0);
  
  if (viewName === 'home') { setGreeting(); hide($('search-results-wrap')); }
  else if (viewName !== 'search') $('main-title').textContent = viewName.charAt(0).toUpperCase() + viewName.slice(1);
  
  if (viewName === 'library') loadLibrary();
}

qq('.nav-btn').forEach(b => b.addEventListener('click', () => switchView(b.dataset.view)));

/* ── History (Recent) ───────────────────────────────────────────────── */
function addToHistory(vid, title, artist, art) {
  // Deduplicate by title+artist since local vids differ
  history = history.filter(h => !(h.title === title && h.artist === artist));
  history.unshift({vid, title, artist, art});
  if (history.length > 30) history.pop();
  
  localStorage.setItem('ttube_history', JSON.stringify(history));
  renderRecent();
}

function renderRecent() {
  const grid = $('recent-grid');
  if (!history.length) {
    grid.innerHTML = '<div class="empty-text">No recent history</div>';
    return;
  }
  grid.innerHTML = history.slice(0, 10).map(h => `
    <div class="card" onclick='instantPlay(${JSON.stringify(h.title)}, ${JSON.stringify(h.artist || "")}, ${JSON.stringify(h.art || "")})'>
      <div class="card-img-wrap">
        <img class="card-img" src="${h.art ? encodeArt(h.art) : 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='}">
        <div class="card-play-btn"><svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg></div>
      </div>
      <div class="card-info">
        <div class="card-title">${escHtml(h.title)}</div>
        <div class="card-artist">${escHtml(h.artist || '')}</div>
      </div>
    </div>
  `).join('');
}

/* ── Trending ───────────────────────────────────────────────────────── */
async function loadTrending() {
  try {
    const r = await fetch('/api/trending?t=' + Date.now());
    const d = await r.json();
    const grid = $('trending-grid');
    if (d.results && d.results.length) {
      grid.innerHTML = d.results.map(t => `
        <div class="card" onclick='instantPlay(${JSON.stringify(t.title)}, ${JSON.stringify(t.artist)}, ${JSON.stringify(t.artwork)})'>
          <div class="card-img-wrap">
            <img class="card-img" src="${t.artwork ? encodeArt(t.artwork) : ''}">
            <div class="card-play-btn"><svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg></div>
          </div>
          <div class="card-info">
            <div class="card-title">${escHtml(t.title)}</div>
            <div class="card-artist">${escHtml(t.artist)}</div>
          </div>
        </div>
      `).join('');
    } else {
      grid.innerHTML = '<div class="empty-text">Could not load trending</div>';
    }
  } catch(e) {
    $('trending-grid').innerHTML = '<div class="empty-text">Error loading trending</div>';
  }
}

async function loadTopArtists() {
  try {
    const r = await fetch('/api/top_artists_list?t=' + Date.now());
    const d = await r.json();
    const sec = $('top-artists-section');
    const grid = $('top-artists-grid');
    if (d.results && d.results.length) {
      grid.innerHTML = d.results.map(a => `
        <div class="artist-card" onclick="openArtist('${escHtml(a.name)}')">
          <div class="artist-card-img-wrap">
            ${a.image ? `<img class="artist-card-img" src="${encodeArt(a.image)}">` : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>`}
          </div>
          <div class="artist-card-name">${escHtml(a.name)}</div>
        </div>
      `).join('');
      show(sec);
    } else {
      hide(sec);
    }
  } catch(e) {
    hide($('top-artists-section'));
  }
}

/* ── Search ─────────────────────────────────────────────────────────── */
const input   = $('search-input');
const suggBox = $('suggestions');
let suggActive = -1;

input.addEventListener('input', () => {
  const v = input.value.trim();
  toggle($('clear-btn'), v.length > 0);
  if (v.length < 2) { hide(suggBox); return; }
  clearTimeout(suggTimer);
  suggTimer = setTimeout(() => fetchSuggestions(v), 380);
});

input.addEventListener('keydown', e => {
  const items = suggBox.querySelectorAll('.sugg-item');
  if (e.key === 'ArrowDown') { e.preventDefault(); suggActive = Math.min(suggActive + 1, items.length - 1); highlightSugg(items); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); suggActive = Math.max(suggActive - 1, -1); highlightSugg(items); }
  else if (e.key === 'Enter') {
    if (suggActive >= 0 && items[suggActive]) { input.value = items[suggActive].dataset.query; }
    hide(suggBox); suggActive = -1; doSearch();
  }
});

function highlightSugg(items) { items.forEach((el, i) => el.classList.toggle('active', i === suggActive)); }
async function fetchSuggestions(q) {
  try {
    const r = await fetch(`${API}/api/suggestions?q=${encodeURIComponent(q)}`);
    const d = await r.json();
    renderSuggestions(d.results || []);
  } catch { hide(suggBox); }
}

function renderSuggestions(results) {
  if (!results.length) { hide(suggBox); return; }
  suggActive = -1;
  suggBox.innerHTML = results.map(s => {
    const q = s.artist ? `${s.track} ${s.artist}` : s.track;
    return `<div class="sugg-item" data-query="${escHtml(q)}" onclick="acceptSuggestion('${escHtml(q)}')">
              ${s.artwork ? `<img class="sugg-art" src="${encodeArt(s.artwork)}">` : ''}
              <div class="sugg-text">
                <div class="sugg-track">${escHtml(s.track)}</div>
                <div class="sugg-artist">${escHtml(s.artist)}</div>
              </div>
            </div>`;
  }).join('');
  show(suggBox);
}

window.acceptSuggestion = q => { input.value = q; hide(suggBox); doSearch(); };
window.clearSearch = () => { input.value = ''; hide($('clear-btn')); hide(suggBox); input.focus(); };

document.addEventListener('click', e => {
  if (!e.target.closest('#search-box') && !e.target.closest('#suggestions')) hide(suggBox);
});

async function doSearchAndPlay(q) {
  input.value = q;
  await doSearch(true);
}

async function instantPlay(title, artist, artwork) {
  $('np-title').textContent = title;
  $('np-artist').textContent = artist || '—';
  if(artwork) {
    $('np-art').src = encodeArt(artwork);
    show($('np-art')); hide($('np-art-ph'));
  }
  show($('loading-ring'));
  $('lyrics-panel').classList.add('show');
  
  try {
    const r = await fetch(`${API}/api/search`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({query: `${title} ${artist}`})
    });
    const d = await r.json();
    if (d.results && d.results.length > 0) {
      const best = d.results[0];
      await fetch(`${API}/api/play`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({
          video_id: best.video_id,
          webpage_url: best.webpage_url,
          title: title,
          artist: artist,
          quality: localStorage.getItem('ttube_quality') || 'standard'
        })
      });
    } else {
      hide($('loading-ring'));
    }
  } catch(e) { hide($('loading-ring')); }
}


async function doSearch(autoPlay = false) {
  const q = input.value.trim();
  if (!q) return;
  hide(suggBox);
  switchView('search');
  $('main-title').textContent = `Search: ${q}`;
  hide($('empty-state')); hide($('search-layout')); hide($('search-error')); show($('search-loading'));
  show($('search-results-wrap'));

  try {
    const r = await fetch(`${API}/api/search`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({query: q})
    });
    const d = await r.json();
    hide($('search-loading'));
    if (d.error) { $('search-error').textContent = '⚠ ' + d.error; show($('search-error')); return; }
    searchResults = d.results || [];
    renderResults(searchResults);
    
    if (autoPlay && searchResults.length > 0) {
      const best = searchResults[0];
      playTrack(best.video_id, best.webpage_url, best.title);
    }
  } catch (err) {
    hide($('search-loading'));
    $('search-error').textContent = '⚠ Network error.';
    show($('search-error'));
  }
}

function renderResults(results) {
  if (!results.length) { $('main-title').textContent = 'No results found'; show($('empty-state')); return; }
  
  const layout = $('search-layout');
  const topRes = $('search-top-result');
  const list = $('search-songs-list');
  
  // Render Top Result (index 0)
  const best = results[0];
  const bestArt = `https://i.ytimg.com/vi/${best.video_id}/hqdefault.jpg`;
  topRes.innerHTML = `
    <h2>Top Result</h2>
    <div class="top-result-card" onclick='playTrack(${JSON.stringify(best.video_id)}, ${JSON.stringify(best.webpage_url)}, ${JSON.stringify(best.title)})'>
      <div class="top-result-img">
        <img src="${bestArt}" onerror="this.src='data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='">
        <div class="top-play-btn"><svg viewBox="0 0 24 24" fill="currentColor"><polygon points="5,3 19,12 5,21"/></svg></div>
      </div>
      <div class="top-result-info">
        <div class="top-result-title">${escHtml(best.title)}</div>
        <div class="top-result-type">Song ${best.offline ? '• <span class="row-offline">OFFLINE</span>' : ''}</div>
      </div>
    </div>
  `;
  
  // Render Songs List (index 1 to 9)
  list.innerHTML = `<h2>Songs</h2>` + results.slice(1).map((r, i) => {
    const art = `https://i.ytimg.com/vi/${r.video_id}/mqdefault.jpg`;
    return `
    <div class="search-list-row${r.video_id === currentVid ? ' playing' : ''}" id="row-${r.video_id}" onclick='playTrack(${JSON.stringify(r.video_id)}, ${JSON.stringify(r.webpage_url)}, ${JSON.stringify(r.title)})'>
      <div class="search-list-img">
        <img src="${art}" onerror="this.src='data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs='">
      </div>
      <div class="search-list-info">
        <div class="search-list-title">${escHtml(r.title)}</div>
      </div>
      <div class="search-list-actions">
        ${r.offline ? '<span class="row-offline">OFFLINE</span>' : ''}
      </div>
    </div>
  `}).join('');
  
  show(layout);
}

/* ── Artists ────────────────────────────────────────────────────────── */
async function loadArtists() {
  try {
    const r = await fetch(`${API}/api/artists`);
    const d = await r.json();
    const list = $('artist-list');
    list.innerHTML = (d.artists || []).map(a => `
      <button class="nav-item" onclick="openArtist('${escHtml(a)}')">${escHtml(a)}</button>
    `).join('');
  } catch(e) {}
}

window.openArtist = async (name) => {
  if (!name || name === '—') return;
  switchView('artist');
  $('artist-title').textContent = name;
  hide($('artist-table')); show($('artist-loading'));
  
  // Follow button status
  const r2 = await fetch(`${API}/api/artists`);
  const d2 = await r2.json();
  const btn = $('artist-follow-btn');
  const isFollowing = (d2.artists || []).includes(name);
  btn.textContent = isFollowing ? 'Following' : 'Follow';
  btn.className = `follow-btn ${isFollowing ? 'following' : ''}`;
  btn.onclick = async () => {
    if (btn.classList.contains('following')) {
      await fetch(`${API}/api/artists/${encodeURIComponent(name)}/unfollow`, {method:'POST'});
      btn.textContent = 'Follow'; btn.classList.remove('following');
    } else {
      await fetch(`${API}/api/artists`, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name})});
      btn.textContent = 'Following'; btn.classList.add('following');
    }
    loadArtists();
  };
  
  try {
    const r = await fetch(`${API}/api/artists/${encodeURIComponent(name)}`);
    const d = await r.json();
    hide($('artist-loading'));
    if (d.tracks && d.tracks.length) {
      $('artist-body').innerHTML = d.tracks.map((t, i) => `
        <tr class="result-row" onclick='instantPlay(${JSON.stringify(t.title)}, ${JSON.stringify(t.artist)}, ${JSON.stringify(t.artwork)})'>
          <td class="row-num">${i+1}</td>
          <td>
            <div class="row-title-wrap">
              <div class="row-title">${escHtml(t.title)}</div>
              <div class="row-artist">${escHtml(t.artist)}</div>
            </div>
          </td>
        </tr>
      `).join('');
      show($('artist-table'));
    }
  } catch(e) { hide($('artist-loading')); }
};


/* ── Library ────────────────────────────────────────────────────────── */
async function loadLibrary() {
  try {
    const r = await fetch(`${API}/api/library`);
    const d = await r.json();
    const body = $('library-body');
    if (!d.tracks || !d.tracks.length) {
      hide($('library-table')); show($('library-empty')); return;
    }
    show($('library-table')); hide($('library-empty'));
    
    body.innerHTML = d.tracks.map((t, i) => `
      <tr class="result-row" onclick='playLocal(${JSON.stringify(t.filename)}, ${JSON.stringify(t.title)}, ${JSON.stringify(t.artist)})'>
        <td class="row-num">${i+1}</td>
        <td style="width:50px; padding-right:0;">
          <div class="row-img-wrap" style="width:40px; height:40px; border-radius:4px; overflow:hidden; background:var(--elevated); display:flex; align-items:center; justify-content:center;">
            ${t.artwork ? `<img src="${t.artwork}" style="width:100%; height:100%; object-fit:cover;">` : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:20px;height:20px;color:var(--gray-dim);"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`}
          </div>
        </td>
        <td>
          <div class="row-title-wrap">
            <div class="row-title">${escHtml(t.title)}</div>
            <div class="row-artist">${escHtml(t.artist)}</div>
          </div>
        </td>
        <td class="col-size">${t.size_mb} MB</td>
        <td class="row-action-cell">
          <button class="row-btn" title="Delete from Library" onclick="event.stopPropagation(); deleteLocal('${escHtml(t.filename)}', '${escHtml(t.title)}')">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18 6L17.1991 18.0129C17.129 19.065 17.0939 19.5911 16.8667 19.99C16.6666 20.3412 16.3648 20.6235 16.0011 20.7998C15.588 21 15.0607 21 14.0062 21H9.99377C8.93927 21 8.41202 21 7.99889 20.7998C7.63517 20.6235 7.33339 20.3412 7.13332 19.99C6.90607 19.5911 6.871 19.065 6.80086 18.0129L6 6M4 6H20M16 6L15.7294 5.18807C15.4671 4.40125 15.3359 4.00784 15.0927 3.71698C14.8779 3.46013 14.6021 3.26132 14.2905 3.13878C13.9376 3 13.523 3 12.6936 3H11.3064C10.477 3 10.0624 3 9.70951 3.13878C9.39792 3.26132 9.12208 3.46013 8.90729 3.71698C8.66405 4.00784 8.53292 4.40125 8.27064 5.18807L8 6M14 10V17M10 10V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
        </td>
      </tr>
    `).join('');
  } catch(e) {}
}

function playLocal(filename, title, artist) {
  currentVid = 'local_' + filename; currentTitle = title;
  updatePlayingRow();
  $('np-title').textContent = title; $('np-artist').textContent = artist || '—';
  show($('loading-ring')); hide($('np-art')); hide($('np-art-skel')); show($('np-art-ph')); hide($('ch-badge'));
  $('pos-time').textContent = '--:--'; $('dur-time').textContent = '--:--';
  $('prog-played').style.width = '0%'; $('prog-buf').style.width = '0%'; $('prog-thumb').style.left = '0%';
  $('lyric-line').textContent = '—';
  $('lyrics-panel').classList.remove('show');
  
  fetch(`${API}/api/play`, {
    method: 'POST', headers: {'Content-Type':'application/json'},
    body: JSON.stringify({filename, title, artist})
  });
}

window.deleteLocal = async (filename, title) => {
  if (confirm(`Delete "${title}" from your library?`)) {
    await fetch(`${API}/api/library/delete`, {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({filename})
    });
    loadLibrary();
  }
};

/* ── Playback ────────────────────────────────────────────────────────── */
window.playTrack = async (vid, url, title) => {
  currentVid = vid; currentTitle = title;
  updatePlayingRow();
  $('np-title').textContent = title; $('np-artist').textContent = '—';
  show($('loading-ring')); hide($('np-art')); hide($('np-art-skel')); show($('np-art-ph')); hide($('ch-badge'));
  $('pos-time').textContent = '--:--'; $('dur-time').textContent = '--:--';
  $('prog-played').style.width = '0%'; $('prog-buf').style.width = '0%'; $('prog-thumb').style.left = '0%';
  $('lyric-line').textContent = '—';
  
  $('lyrics-panel').classList.remove('show');
  
  try {
    await fetch(`${API}/api/play`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({video_id: vid, webpage_url: url, title})
    });
  } catch {}
};

window.togglePause = async () => {
  try { const r = await fetch(`${API}/api/pause`, {method:'POST'}); const d = await r.json(); setPauseIcon(d.paused); } catch {}
};

window.stopPlayback = async () => {
  try {
    await fetch(`${API}/api/stop`, {method:'POST'});
    currentVid = ''; updatePlayingRow();
    $('np-title').textContent = '—'; $('np-artist').textContent = '—';
    hide($('np-art')); show($('np-art-ph')); hide($('np-art-skel')); hide($('ch-badge'));
    $('pos-time').textContent = '--:--'; $('dur-time').textContent = '--:--';
    $('prog-played').style.width = '0%'; $('prog-buf').style.width = '0%'; $('prog-thumb').style.left = '0%';
    setPauseIcon(false); $('lyric-line').textContent = '—';
    $('lyrics-panel').classList.remove('show');
    $('vu-l').style.width = '0%'; $('vu-r').style.width = '0%';
  } catch {}
};

window.seekRel = async (delta) => {
  await fetch(`${API}/api/seek_rel`, {
    method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({delta})
  });
};

function setPauseIcon(paused) { toggle($('icon-play'), paused); toggle($('icon-pause'), !paused); }

/* ── Seek Bar ────────────────────────────────────────────────────────── */
let _seekDur = null;
window.startSeek = e => {
  e.preventDefault(); seekDragging = true; doSeekAt(e);
  const move = ev => { if (seekDragging) doSeekAt(ev); };
  const up = async ev => {
    if (!seekDragging) return;
    seekDragging = false; document.removeEventListener('mousemove', move); document.removeEventListener('mouseup', up);
    const pos = calcSeekPos(ev);
    if (pos !== null) {
      await fetch(`${API}/api/seek`, {
        method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify({position: pos})
      });
    }
  };
  document.addEventListener('mousemove', move); document.addEventListener('mouseup', up);
};
function doSeekAt(e) {
  const pos = calcSeekPos(e);
  if (pos !== null && _seekDur) {
    const pct = (pos / _seekDur) * 100;
    $('prog-played').style.width = pct + '%'; $('prog-thumb').style.left = pct + '%';
    $('pos-time').textContent = fmt(pos);
  }
}
function calcSeekPos(e) {
  const rect = $('progress-wrap').getBoundingClientRect();
  const x = (e.clientX ?? e.touches?.[0]?.clientX ?? 0) - rect.left;
  const ratio = Math.max(0, Math.min(1, x / rect.width));
  return _seekDur ? ratio * _seekDur : null;
}

/* ── Download ────────────────────────────────────────────────────────── */
window.downloadTrack = async (vid, url, title, artist = '') => {
  try {
    const r = await fetch(`${API}/api/download`, {
      method: 'POST', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({video_id: vid, webpage_url: url, title, artist})
    });
    const d = await r.json();
    if (d.already) showStatus(`Already downloaded: ${title}`);
    else showStatus('Download started...');
  } catch {}
};

/* ── Playlists ───────────────────────────────────────────────────────── */
async function loadPlaylists() {
  try {
    const r = await fetch(`${API}/api/playlists`);
    const d = await r.json();
    allPlaylists = d.playlists || [];
    const list = $('playlist-list');
    list.innerHTML = allPlaylists.map(p => `
      <button class="nav-item" onclick="openPlaylist('${escHtml(p.name)}')">${escHtml(p.name)}</button>
    `).join('');
  } catch(e) {}
}

window.createPlaylist = () => {
  $('new-pl-input').value = '';
  show($('new-pl-modal'));
  setTimeout(() => $('new-pl-input').focus(), 100);
};
window.closeNewPlModal = () => { hide($('new-pl-modal')); };
window.submitNewPlaylist = async () => {
  const name = $('new-pl-input').value.trim();
  if (!name) return;
  closeNewPlModal();
  await fetch(`${API}/api/playlists`, { method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({name}) });
  loadPlaylists();
};
$('new-pl-input')?.addEventListener('keydown', e => { if (e.key === 'Enter') submitNewPlaylist(); });

window.openPlModal = (vid, url, title) => {
  if (allPlaylists.length === 1) {
    // Only Liked Songs, add directly
    addToPlaylist(allPlaylists[0].name, vid, url, title);
    return;
  }
  plModalVid = vid; plModalUrl = url; plModalTitle = title;
  const list = $('modal-pl-list');
  list.innerHTML = allPlaylists.map(p => `
    <button class="modal-item" onclick="addToPlaylist('${escHtml(p.name)}', '${escHtml(vid)}', '${escHtml(url)}', '${escHtml(title)}')">
      ${escHtml(p.name)}
    </button>
  `).join('');
  show($('playlist-modal'));
};
window.closeModal = () => { hide($('playlist-modal')); };

window.addToPlaylist = (name, vid, url, title) => {
  fetch(`${API}/api/playlists/${encodeURIComponent(name)}/add`, {
    method: 'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({video_id: vid, webpage_url: url, title})
  }).then(()=> { showStatus(`Added to ${name}`); closeModal(); }).then(loadPlaylists);
};

window.openPlaylist = async (name) => {
  try {
    const r = await fetch(`${API}/api/playlists/${encodeURIComponent(name)}`);
    const d = await r.json();
    switchView('playlist');
    $('pl-title').textContent = d.name;
    
    if (d.name === 'Liked Songs') hide($('pl-delete-btn'));
    else {
      show($('pl-delete-btn'));
      $('pl-delete-btn').onclick = async () => {
        if(confirm(`Delete playlist ${d.name}?`)) {
          await fetch(`${API}/api/playlists/${encodeURIComponent(d.name)}`, {method:'DELETE'});
          loadPlaylists(); switchView('home');
        }
      };
    }

    $('pl-body').innerHTML = d.tracks.map((t, i) => `
      <tr class="result-row" onclick='playTrack(${JSON.stringify(t.video_id)}, ${JSON.stringify(t.webpage_url)}, ${JSON.stringify(t.title)})'>
        <td class="row-num">${i+1}</td>
        <td style="width:50px; padding-right:0;">
          <div class="row-img-wrap" style="width:40px; height:40px; border-radius:4px; overflow:hidden; background:var(--elevated); display:flex; align-items:center; justify-content:center;">
            ${t.artwork_url ? `<img src="${encodeArt(t.artwork_url)}" style="width:100%; height:100%; object-fit:cover;">` : `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="width:20px;height:20px;color:var(--gray-dim);"><path d="M9 18V5l12-2v13"></path><circle cx="6" cy="18" r="3"></circle><circle cx="18" cy="16" r="3"></circle></svg>`}
          </div>
        </td>
        <td>
          <div class="row-title-wrap">
            <div class="row-title">${escHtml(t.title)}</div>
            <div class="row-artist">${escHtml(t.artist || '')}</div>
          </div>
        </td>
        <td class="row-action-cell">
          <button class="row-btn" title="Remove from Playlist" onclick="event.stopPropagation(); removePlTrack('${escHtml(d.name)}', '${escHtml(t.video_id)}')">
            <svg viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg"><path d="M18 6L17.1991 18.0129C17.129 19.065 17.0939 19.5911 16.8667 19.99C16.6666 20.3412 16.3648 20.6235 16.0011 20.7998C15.588 21 15.0607 21 14.0062 21H9.99377C8.93927 21 8.41202 21 7.99889 20.7998C7.63517 20.6235 7.33339 20.3412 7.13332 19.99C6.90607 19.5911 6.871 19.065 6.80086 18.0129L6 6M4 6H20M16 6L15.7294 5.18807C15.4671 4.40125 15.3359 4.00784 15.0927 3.71698C14.8779 3.46013 14.6021 3.26132 14.2905 3.13878C13.9376 3 13.523 3 12.6936 3H11.3064C10.477 3 10.0624 3 9.70951 3.13878C9.39792 3.26132 9.12208 3.46013 8.90729 3.71698C8.66405 4.00784 8.53292 4.40125 8.27064 5.18807L8 6M14 10V17M10 10V17" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>
          </button>
        </td>
      </tr>
    `).join('');
  } catch(e) {}
};

window.removePlTrack = async (plName, vid) => {
  await fetch(`${API}/api/playlists/${encodeURIComponent(plName)}/remove`, {
    method: 'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({video_id: vid})
  });
  openPlaylist(plName); // refresh
};

/* ── Status polling ──────────────────────────────────────────────────── */
async function poll() {
  try {
    const r = await fetch(`${API}/api/status`);
    const s = await r.json();
    applyStatus(s);
    lastStatus = s;
  } catch {}
}

function applyStatus(s) {
  toggle($('loading-ring'), s.loading);
  if (!s.playing && !s.loading && !s.paused) setPauseIcon(false);
  else setPauseIcon(s.paused);
  
  // Lyrics panel visibility
  if (s.playing || s.paused || s.loading || s.meta_loading) {
    if (!$('lyrics-panel').classList.contains('show')) $('lyrics-panel').classList.add('show');
  } else {
    $('lyrics-panel').classList.remove('show');
  }

  // Meta loading skeletons
  if (s.meta_loading) {
    hide($('np-art')); hide($('np-art-ph')); show($('np-art-skel'));
    hide($('np-info-content')); show($('np-info-skel'));
  } else {
    hide($('np-art-skel')); hide($('np-info-skel')); show($('np-info-content'));
    
    if (s.title && s.title !== $('np-title').textContent) $('np-title').textContent = s.title;
    if (s.artist || s.album) {
      const sub = [s.artist, s.album].filter(Boolean).join('  ·  ');
      if (sub !== $('np-artist').textContent) {
        $('np-artist').textContent = sub; currentArtist = s.artist;
        if (s.playing && currentVid) addToHistory(currentVid, s.title, s.artist, s.artwork);
      }
    }

    if (s.artist && currentVid) {
      qq(`#row-${CSS.escape(currentVid)} .row-artist`).forEach(el => {
        if (el.textContent === '—') el.textContent = s.artist;
      });
    }

    if (s.artwork && s.artwork !== lastStatus.artwork) {
      const img = $('np-art');
      img.onload = () => { show(img); hide($('np-art-ph')); };
      img.onerror = () => { hide(img); show($('np-art-ph')); };
      img.src = encodeArt(s.artwork);
    } else if (s.artwork && lastStatus.artwork && !s.meta_loading) {
      // Re-show cached artwork if meta_loading hid it previously
      show($('np-art')); hide($('np-art-ph'));
    } else if (!s.artwork && lastStatus.artwork && !s.meta_loading) {
      hide($('np-art')); show($('np-art-ph'));
    }
  }

  if (s.channel_label && s.playing) { $('ch-badge').textContent = s.channel_label; show($('ch-badge')); }
  else hide($('ch-badge'));

  _seekDur = s.duration;
  if (!seekDragging) {
    $('pos-time').textContent = s.pos_fmt || '--:--';
    $('dur-time').textContent = s.dur_fmt || '--:--';
    if (s.duration && s.position != null) {
      const pp = Math.min(100, (s.position / s.duration) * 100);
      const bp = s.buffered ? Math.min(100, ((s.position + s.buffered) / s.duration) * 100) : pp;
      $('prog-played').style.width = pp + '%';
      $('prog-buf').style.width = bp + '%';
      $('prog-thumb').style.left = pp + '%';
    }
  }

  const [l, r] = s.levels || [0, 0];
  $('vu-l').style.width = Math.min(100, l * 100) + '%';
  $('vu-r').style.width = Math.min(100, r * 100) + '%';

  if (s.lyric && s.playing && !s.paused) {
    const lineEl = $('lyric-line');
    if (lineEl.textContent !== s.lyric) {
      lineEl.style.animation = 'none';
      lineEl.offsetHeight; // trigger reflow
      lineEl.textContent = s.lyric;
      lineEl.style.animation = 'lyricFadeIn 0.5s cubic-bezier(0.2, 0.8, 0.2, 1) forwards';
    }
  } else {
    if (!$('lyric-line').textContent.startsWith('—')) $('lyric-line').textContent = '—';
  }
  if (typeof updateLyricsUI === 'function') updateLyricsUI(s.lyric, encodeArt(s.artwork));


  const dl = s.download;
  if (dl && dl.status !== 'done' && dl.status !== 'error') {
    $('dl-name').textContent = dl.display || ''; $('dl-pct').textContent = dl.progress + '%';
    $('dl-bar').style.width = dl.progress + '%'; show($('dl-widget'));
  } else {
    hide($('dl-widget'));
    if (dl?.status === 'done') { showStatus('✓ Downloaded successfully'); loadLibrary(); }
    if (dl?.status === 'error') showStatus('✗ Download failed: ' + dl.error);
  }

  if (s.current_vid !== lastStatus.current_vid) { currentVid = s.current_vid || ''; updatePlayingRow(); }
}

function updatePlayingRow() {
  qq('.result-row').forEach(row => {
    const vid = row.id.replace('row-', '');
    row.classList.toggle('playing', vid === currentVid);
  });
}

let statusTimer = null;
function showStatus(msg) {
  const el = $('status-msg'); el.textContent = msg; show(el);
  clearTimeout(statusTimer); statusTimer = setTimeout(() => hide(el), 4000);
}

document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === ' ') { e.preventDefault(); togglePause(); }
  if (e.key === 's' || e.key === 'S') stopPlayback();
});

setInterval(() => fetch(`${API}/api/heartbeat`, {method:'POST'}).catch(e=>e), 20000);

/* ── Boot ────────────────────────────────────────────────────────────── */
setGreeting();
loadPlaylists();
loadArtists();
renderRecent();
loadTrending();
loadTopArtists();
switchView('home');
poll();
setInterval(poll, 500);

function showToast(msg) {
  let t = document.createElement('div');
  t.className = 'toast show';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => { t.classList.remove('show'); setTimeout(()=>t.remove(), 300); }, 1500);
}

// Global Keyboard Controls
document.addEventListener('keydown', e => {
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
  if (e.key === 'ArrowLeft') {
    e.preventDefault();
    seekRel(-10);
    showToast("-10s");
  } else if (e.key === 'ArrowRight') {
    e.preventDefault();
    seekRel(10);
    showToast("+10s");
  }
});

// Horizontal Scrolling via Event Delegation
document.addEventListener('wheel', e => {
  const grid = e.target.closest('.cards-grid');
  if (grid && e.deltaY !== 0) {
    if (Math.abs(e.deltaY) > Math.abs(e.deltaX)) {
      e.preventDefault();
      grid.scrollBy({ left: e.deltaY, behavior: 'auto' });
    }
  }
}, { passive: false });

window.scrollGrid = function(id, amt) {
  const grid = document.getElementById(id);
  if (grid) {
    grid.scrollBy({ left: amt, behavior: 'smooth' });
  }
};






/* ── NEW UI LOGIC ── */

// User & Theme Init
let curUser = localStorage.getItem('ttube_username') || 'Guest';
let curAvatar = localStorage.getItem('ttube_avatar') || '';



function initUserProfile() {
  $('user-name-txt').textContent = curUser;
  if (curAvatar) $('user-avatar-img').src = curAvatar;
  
  $('greeting').textContent = `Good ${new Date().getHours() < 12 ? 'Morning' : (new Date().getHours() < 18 ? 'Afternoon' : 'Evening')}, ${curUser}`;
}

// Onboarding Wizard
if (!localStorage.getItem('ttube_onboarded')) {
  show($('onboarding-wizard'));
} else {
  initUserProfile();
}

function nextOnboardStep(step) {
  qq('.onboard-step').forEach(s => s.classList.remove('active', 'done'));
  for (let i = 1; i < step; i++) {
    const s = $(`onboard-step-${i}`);
    if(s) { s.classList.remove('active'); s.classList.add('done'); }
  }
  const cur = $(`onboard-step-${step}`);
  if(cur) { cur.classList.remove('done'); cur.classList.add('active'); }
}

`
function finishOnboarding() {
  const name = $('onboard-name-input').value.trim() || 'Guest';
  const avatar = $('onboard-avatar-input').value.trim();
  localStorage.setItem('ttube_onboarded', '1');
  localStorage.setItem('ttube_username', name);
  localStorage.setItem('ttube_avatar', avatar);
  localStorage.setItem('ttube_quality', $('setting-quality').value);
  curUser = name; curAvatar = avatar;
  initUserProfile();
  $('onboarding-wizard').style.opacity = '0';
  setTimeout(() => hide($('onboarding-wizard')), 800);
}

// Settings Modal
function openSettings() {
  $('setting-username').value = curUser === 'Guest' ? '' : curUser;
  $('setting-avatar').value = curAvatar;
  
  $('setting-quality').value = localStorage.getItem('ttube_quality') || 'standard';
  show($('settings-modal'));
}

function closeSettings() {
  hide($('settings-modal'));
}


function saveSettings() {
  const name = $('setting-username').value.trim() || 'Guest';
  const avatar = $('setting-avatar').value.trim();
  localStorage.setItem('ttube_username', name);
  localStorage.setItem('ttube_avatar', avatar);
  localStorage.setItem('ttube_quality', $('setting-quality').value);
  curUser = name; curAvatar = avatar;
  initUserProfile();
  closeSettings();
}

async function eraseAllData() {
  if (!confirm("WARNING: This will permanently delete ALL downloaded songs, playlists, and settings. This cannot be undone. Are you sure?")) return;
  try {
    const r = await fetch('/api/erase_data', { method: 'POST' });
    if (r.ok) {
      localStorage.clear();
      window.location.reload();
    } else {
      alert("Failed to erase backend data.");
    }
  } catch (e) {
    alert("Error erasing data.");
  }
}

// Lyrics Modal
let lyricsOpen = false;
let currentLyricText = '';

function toggleLyricsModal() {
  lyricsOpen = !lyricsOpen;
  const mod = $('lyrics-modal');
  const btn = $('lyrics-toggle-btn');
  if (lyricsOpen) {
    mod.classList.add('active');
    btn.classList.add('active');
  } else {
    mod.classList.remove('active');
    btn.classList.remove('active');
  }
}

function updateLyricsUI(lyric, artwork) {
  if (!lyricsOpen) return;
  if ($('lyrics-bg-blur') && artwork) {
    $('lyrics-bg-blur').style.backgroundImage = `url('${artwork}')`;
  }
  
  if (lyric && lyric !== currentLyricText) {
    currentLyricText = lyric;
    const wrap = $('lyrics-content-wrap');
    // Smooth crossfade logic
    wrap.innerHTML = `<div class="lyric-line active" style="font-size: 2rem; color: #fff;">${escHtml(lyric)}</div>`;
  } else if (!lyric && currentLyricText) {
    currentLyricText = '';
    $('lyrics-content-wrap').innerHTML = `<div class="lyric-line active" style="opacity:0.3; font-size: 2rem;">...</div>`;
  }
}

