
/* ── NEW UI LOGIC ── */

// User & Theme Init
let curTheme = localStorage.getItem('ttube_theme') || 'purple';
let curUser = localStorage.getItem('ttube_username') || 'Guest';
let curAvatar = localStorage.getItem('ttube_avatar') || '';

const THEMES = {
  purple: '#7c3aed', blue: '#2563eb', green: '#10b981', red: '#ef4444'
};

function applyTheme(colorName) {
  const hex = THEMES[colorName] || THEMES.purple;
  document.documentElement.style.setProperty('--primary', hex);
  // Also calculate hover state (slightly brighter)
  document.documentElement.style.setProperty('--primary-hl', hex); 
}

function initUserProfile() {
  $('user-name-txt').textContent = curUser;
  if (curAvatar) $('user-avatar-img').src = curAvatar;
  applyTheme(curTheme);
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

function setThemePreview(color) {
  applyTheme(color);
  curTheme = color;
  qq('#onboard-step-3 .color-swatch').forEach(s => s.classList.remove('active'));
  document.querySelector(`#onboard-step-3 .color-swatch.${color}`).classList.add('active');
}

function finishOnboarding() {
  const name = $('onboard-name-input').value.trim() || 'Guest';
  const avatar = $('onboard-avatar-input').value.trim();
  localStorage.setItem('ttube_onboarded', '1');
  localStorage.setItem('ttube_username', name);
  localStorage.setItem('ttube_avatar', avatar);
  localStorage.setItem('ttube_theme', curTheme);
  curUser = name; curAvatar = avatar;
  initUserProfile();
  $('onboarding-wizard').style.opacity = '0';
  setTimeout(() => hide($('onboarding-wizard')), 800);
}

// Settings Modal
function openSettings() {
  $('setting-username').value = curUser === 'Guest' ? '' : curUser;
  $('setting-avatar').value = curAvatar;
  qq('.settings-modal-box .color-swatch').forEach(s => s.classList.remove('active'));
  const sw = document.querySelector(`.settings-modal-box .color-swatch.${curTheme}`);
  if(sw) sw.classList.add('active');
  show($('settings-modal'));
}

function closeSettings() {
  hide($('settings-modal'));
}

function setTheme(color) {
  curTheme = color;
  qq('.settings-modal-box .color-swatch').forEach(s => s.classList.remove('active'));
  document.querySelector(`.settings-modal-box .color-swatch.${color}`).classList.add('active');
}

function saveSettings() {
  const name = $('setting-username').value.trim() || 'Guest';
  const avatar = $('setting-avatar').value.trim();
  localStorage.setItem('ttube_username', name);
  localStorage.setItem('ttube_avatar', avatar);
  localStorage.setItem('ttube_theme', curTheme);
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
    wrap.innerHTML = `<div class="lyric-line active" style="animation: fadeIn 0.5s;">${escHtml(lyric)}</div>`;
  } else if (!lyric && currentLyricText) {
    currentLyricText = '';
    $('lyrics-content-wrap').innerHTML = `<div class="lyric-line active" style="opacity:0.5;">♪ ♫ ♪</div>`;
  }
}

