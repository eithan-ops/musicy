/* Dynamic share images: /api/og?c=<challenge id> (someone's time to beat) or /api/og?room=<code> (a room waiting for you).
   Renders with @vercel/og on the edge; fonts and characters come from the site itself. */
import { ImageResponse } from '@vercel/og';
export const config = { runtime: 'edge' };

const SB = 'https://ludpwcctxblpdqnijgyq.supabase.co';  /* the public anon key is the same one the page ships with */
const SB_ANON = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imx1ZHB3Y2N0eGJscGRxbmlqZ3lxIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzY4Njg3MzMsImV4cCI6MjA5MjQ0NDczM30.r5xiCxaci3lXT-_srTdIrdeRKV1yCc3-FJNggntEy-o';
const ORIGIN = 'https://musicy.fun';
let fontCache = null;
async function fonts(){
  if (fontCache) return fontCache;
  const [rubik, secular] = await Promise.all([
    fetch(ORIGIN + '/og/rubik-700.woff').then(r => r.arrayBuffer()),
    fetch(ORIGIN + '/og/secular-one.woff').then(r => r.arrayBuffer())]);
  return (fontCache = [{ name: 'Rubik', data: rubik, weight: 700, style: 'normal' }, { name: 'Secular One', data: secular, weight: 400, style: 'normal' }]);
}
/* satori lays text out left-to-right with no bidi: flip a Hebrew line into visual order (Hebrew runs reversed, digits/Latin kept) */
const HEB = /[\u0590-\u05FF]/;
function bidi(s){ if (!HEB.test(s)) return s; const runs = s.match(/[\u0590-\u05FF\s.,·:!?()'"״׳-]+|[^\u0590-\u05FF]+/g) || [s];
  return runs.reverse().map(r => HEB.test(r) || /^[\s.,·:!?()'"״׳-]+$/.test(r) ? [...r].reverse().join('') : r).join(''); }
const fmt = ms => { const s = Math.round(ms / 1000); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
const CHARS = ['sax', 'guitar', 'drums', 'synth', 'violin'];

export default async function handler(req){
  const url = new URL(req.url), c = url.searchParams.get('c'), room = url.searchParams.get('room'), t = url.searchParams.get('t'), lang = url.searchParams.get('lang') === 'en' ? 'en' : 'he';
  let chars = CHARS;
  let kicker = '', title = lang === 'en' ? 'The band falls apart. You put it back.' : 'הלהקה מתפרקת. אתם מחזירים אותה.', stat = '', pill = lang === 'en' ? 'Music party game · No sign-up' : 'משחק מוזיקה · בלי הרשמה';
  if (c){
    try {
      const base = process.env.SUPABASE_URL || SB, key = process.env.SUPABASE_ANON_KEY || SB_ANON;
      const r = await fetch(`${base}/rest/v1/musicy_challenges?id=eq.${encodeURIComponent(c.toUpperCase())}&select=band_name,time_ms,stars,players`, { headers: { apikey: key, Authorization: 'Bearer ' + key } });
      const j = r.ok ? await r.json() : [];
      if (j[0]){ const x = j[0];
        kicker = lang === 'en' ? 'You got a challenge' : 'קיבלתם אתגר';
        title = lang === 'en' ? `${x.band_name} fixed the song in ${fmt(x.time_ms)}` : `${x.band_name} הרכיבו את השיר ב-${fmt(x.time_ms)}`;
        stat = '★'.repeat(x.stars || 0) + '☆'.repeat(3 - (x.stars || 0));
        pill = lang === 'en' ? 'Can you beat them?' : 'אתם תצליחו מהר יותר?'; }
    } catch(e){}
  } else if (t && /^[a-z0-9_-]{2,40}$/.test(t)){
    /* a song's own page: its title, artist and its own band */
    try { const j = await (await fetch(ORIGIN + '/tracks/index.json')).json(); const song = (j.tracks || []).find(x => x.id === t);
      if (song){ kicker = lang === 'en' ? (song.artist_en || song.artist || '') : (song.artist || song.artist_en || ''); title = lang === 'en' ? (song.title_en || song.title) : song.title;
        pill = lang === 'en' ? 'Can you put it back?' : 'תצליחו להחזיר אותו?'; stat = '';
        const ROLE_CH = { drums: 'drums', bass: 'bass', chords: 'keys', arp: 'guitar', melody: 'synth', perc: 'perc', counter: 'trumpet' };
        const byName = n => { n = String(n || ''); return /sax|סקס/i.test(n) ? 'sax' : /violin|string|כינור|מיתר/i.test(n) ? 'violin' : /cello|צ׳לו/i.test(n) ? 'cello' : /flute|חליל/i.test(n) ? 'flute' : /trumpet|brass|horn|חצוצר|נשיפה/i.test(n) ? 'trumpet' : /marimba|bell|steel|מרימב|פעמונ|סטיל/i.test(n) ? 'marimba' : /banjo|בנג׳ו/i.test(n) ? 'banjo' : /accordion|אקורדיון/i.test(n) ? 'accordion' : /perc|darbuka|shaker|הקשה|דרבוק/i.test(n) ? 'perc' : /guitar|oud|גיטרה|עוד/i.test(n) ? 'guitar' : /piano|keys|פסנתר|קליד/i.test(n) ? 'keys' : null; };
        const list = (song.stems || []).map(x => byName((x.name_en || '') + ' ' + (x.name || '')) || ROLE_CH[x.role] || 'synth');
        if (list.length) chars = list.slice(0, 5); } } catch(e){}
  } else if (room){
    kicker = lang === 'en' ? 'A room is waiting for you' : 'חדר מחכה לכם';
    title = lang === 'en' ? `Join room ${room}` : `הצטרפו לחדר ${room}`;
    pill = lang === 'en' ? 'Tap the link to join' : 'לוחצים על הלינק ומצטרפים';
  }
  const f = await fonts();
  return new ImageResponse(
    { type: 'div', props: { style: { width: 1200, height: 630, display: 'flex', flexDirection: 'column', background: '#3A2EF0', color: '#fff', fontFamily: 'Rubik', position: 'relative', direction: 'ltr' }, children: [
      { type: 'div', props: { style: { position: 'absolute', left: 150, right: 150, top: 180, height: 520, borderRadius: 400, background: 'radial-gradient(closest-side, rgba(130,110,255,.75), transparent)' } } },
      { type: 'div', props: { style: { position: 'absolute', left: 56, top: 36, fontFamily: 'Secular One', fontSize: 54, direction: 'ltr' }, children: 'Musicy' } },
      { type: 'div', props: { style: { position: 'absolute', right: 56, top: 48, background: '#FFD23F', color: '#14112B', border: '4px solid #14112B', borderRadius: 999, padding: '8px 26px', fontSize: 26, boxShadow: '5px 5px 0 #14112B' }, children: bidi(pill) } },
      { type: 'div', props: { style: { position: 'absolute', left: 0, right: 0, top: 150, display: 'flex', justifyContent: 'center', alignItems: 'flex-end', gap: 14, direction: 'ltr' },
        children: chars.map((k, i) => ({ type: 'img', props: { src: `${ORIGIN}/og/ch-${k}.png`, style: { height: i === Math.floor(chars.length / 2) ? 270 : 230 } } })) } },
      kicker ? { type: 'div', props: { style: { position: 'absolute', left: 0, right: 0, top: 418, display: 'flex', justifyContent: 'center', fontSize: 28, color: '#FFD23F' }, children: bidi(kicker) } } : null,
      { type: 'div', props: { style: { position: 'absolute', left: 40, right: 40, top: kicker ? 452 : 440, display: 'flex', justifyContent: 'center', fontFamily: 'Secular One', fontSize: title.length > 34 ? 46 : 58, lineHeight: 1.05, textShadow: '4px 4px 0 #14112B', textAlign: 'center' }, children: bidi(title) } },
      { type: 'div', props: { style: { position: 'absolute', left: 0, right: 0, top: 545, display: 'flex', justifyContent: 'center', gap: 18, fontSize: 30, color: '#E6E4FF' }, children: [
        stat ? { type: 'div', props: { style: { color: '#F2B705', fontSize: 34 }, children: stat } } : null,
        { type: 'div', props: { style: { color: '#FFD23F', direction: 'ltr' }, children: 'musicy.fun' } } ].filter(Boolean) } }
    ].filter(Boolean) } },
    { width: 1200, height: 630, fonts: f, headers: { 'cache-control': 'public, max-age=3600, s-maxage=86400' } });
}
