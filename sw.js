/* Musicy service worker: the app shell opens instantly and works offline; the last songs you played stay cached.
   Bump SHELL when the shell files change (index.html is always fetched network-first, so it only matters for the static assets). */
const SHELL = 'musicy-shell-v1';
const TRACKS = 'musicy-tracks-v1';
const SHELL_FILES = ['/', '/manifest.json', '/icon.svg', '/icons/icon-192.png', '/icons/icon-512.png',
  '/chars/m/drums.webp', '/chars/m/bass.webp', '/chars/m/keys.webp', '/chars/m/guitar.webp', '/chars/m/violin.webp', '/chars/m/cello.webp', '/chars/m/sax.webp',
  '/chars/m/synth.webp', '/chars/m/accordion.webp', '/chars/m/trumpet.webp', '/chars/m/marimba.webp', '/chars/m/banjo.webp', '/chars/m/flute.webp', '/chars/m/perc.webp'];
const MAX_TRACK_DIRS = 6;  /* keep the last six songs (each is one folder of stems) */

self.addEventListener('install', e => {
  e.waitUntil(caches.open(SHELL).then(c => c.addAll(SHELL_FILES).catch(() => {})).then(() => self.skipWaiting()));
});
self.addEventListener('activate', e => {
  e.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k !== SHELL && k !== TRACKS).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});

const isTrack = url => /^\/tracks\/[^/]+\/[^/]+\.(flac|m4a|mp3|opus)$/.test(url.pathname);
const isShellAsset = url => /^\/(chars|icons|og)\//.test(url.pathname) || url.pathname === '/manifest.json' || url.pathname === '/icon.svg';

self.addEventListener('fetch', e => {
  const req = e.request; if (req.method !== 'GET') return;
  const url = new URL(req.url); if (url.origin !== location.origin) return;
  if (url.pathname.startsWith('/api/')) return;

  /* navigations and the catalog: network first, cached fallback (so a deploy is picked up right away, and the app still opens on the train) */
  if (req.mode === 'navigate' || url.pathname === '/tracks/index.json'){
    e.respondWith(fetch(req).then(r => { if (r.ok){ const copy = r.clone(); caches.open(SHELL).then(c => c.put(req.mode === 'navigate' ? '/' : req, copy)); } return r; })
      .catch(() => caches.match(req.mode === 'navigate' ? '/' : req)));
    return;
  }
  /* stems: cache first, then trim to the last few songs */
  if (isTrack(url)){
    e.respondWith(caches.open(TRACKS).then(async c => { const hit = await c.match(req); if (hit) return hit;
      const r = await fetch(req); if (r.ok){ c.put(req, r.clone()); trimTracks(c); } return r; }));
    return;
  }
  /* characters, icons: cache first */
  if (isShellAsset(url)){
    e.respondWith(caches.open(SHELL).then(async c => { const hit = await c.match(req); if (hit) return hit; const r = await fetch(req); if (r.ok) c.put(req, r.clone()); return r; }));
  }
});

async function trimTracks(c){
  try { const keys = await c.keys(); const dirs = []; keys.forEach(k => { const d = new URL(k.url).pathname.split('/')[2]; if (!dirs.includes(d)) dirs.push(d); });
    while (dirs.length > MAX_TRACK_DIRS){ const old = dirs.shift(); for (const k of keys) if (new URL(k.url).pathname.split('/')[2] === old) await c.delete(k); } } catch(e){}
}
