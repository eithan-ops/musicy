/* Share previews for challenge and room links: the same app shell, with the og/twitter tags swapped for a dynamic image
   (WhatsApp, Telegram and iMessage render the preview from these tags, so a bare link already shows the band and the time to beat). */
export const config = { matcher: ['/c/:id', '/:code(\\d{4})', '/t/:id'] };

export default async function middleware(req){
  const url = new URL(req.url), m = url.pathname.match(/^\/c\/([A-Za-z0-9]{5})\/?$/), r = url.pathname.match(/^\/(\d{4})\/?$/), t = url.pathname.match(/^\/t\/([a-z0-9_-]{2,40})\/?$/);
  if (!m && !r && !t) return;
  const shell = await fetch(new URL('/', url.origin), { headers: { 'x-musicy-shell': '1' } });
  if (!shell.ok) return;
  let html = await shell.text();
  const lang = (req.headers.get('x-vercel-ip-country') || '') && req.headers.get('x-vercel-ip-country') !== 'IL' ? 'en' : 'he';
  /* a song's own page: its title and artist from the catalog */
  let song = null;
  if (t){ try { const j = await (await fetch(new URL('/tracks/index.json', url.origin))).json(); song = (j.tracks || []).find(x => x.id === t[1]) || null; } catch(e){} }
  const sTitle = song ? (lang === 'en' ? (song.title_en || song.title) : song.title) : '', sArtist = song ? (lang === 'en' ? (song.artist_en || song.artist) : song.artist) : '';
  const img = m ? `${url.origin}/api/og?c=${encodeURIComponent(m[1].toUpperCase())}&lang=${lang}` : t ? `${url.origin}/api/og?t=${encodeURIComponent(t[1])}&lang=${lang}` : `${url.origin}/api/og?room=${r[1]}&lang=${lang}`;
  const title = m ? (lang === 'en' ? 'Musicy · You got a challenge' : 'Musicy · קיבלתם אתגר') : t ? (song ? `Musicy · ${sTitle}` : 'Musicy') : (lang === 'en' ? `Musicy · Join room ${r[1]}` : `Musicy · הצטרפו לחדר ${r[1]}`);
  const desc = m ? (lang === 'en' ? 'Same song, same mess. Can you fix the band faster?' : 'אותו שיר ואותו בלגן. תצליחו להחזיר את הלהקה מהר יותר?')
             : t ? (song ? (lang === 'en' ? `${sArtist} · the song fell apart into ${(song.stems || []).length} instruments. Can you put it back?` : `${sArtist} · השיר התפרק ל-${(song.stems || []).length} כלים. תצליחו להחזיר אותו?`) : (lang === 'en' ? 'The band falls apart. You put it back.' : 'הלהקה מתפרקת. אתם מחזירים אותה.'))
                 : (lang === 'en' ? 'One phone plays, everyone gets an instrument. Tap to join.' : 'טלפון אחד מנגן, כל חבר מקבל כלי. לוחצים ומצטרפים.');
  html = html
    .replace(/<meta property="og:image" content="[^"]*">/, `<meta property="og:image" content="${img}">`)
    .replace(/<meta name="twitter:image" content="[^"]*">/, `<meta name="twitter:image" content="${img}">`)
    .replace(/<meta property="og:title" content="[^"]*">/, `<meta property="og:title" content="${title}">`)
    .replace(/<meta name="twitter:title" content="[^"]*">/, `<meta name="twitter:title" content="${title}">`)
    .replace(/<meta property="og:description" content="[^"]*">/, `<meta property="og:description" content="${desc}">`)
    .replace(/<meta name="twitter:description" content="[^"]*">/, `<meta name="twitter:description" content="${desc}">`)
    .replace(/<meta property="og:url" content="[^"]*">/, `<meta property="og:url" content="${url.origin}${url.pathname}">`);
  return new Response(html, { status: 200, headers: { 'content-type': 'text/html; charset=utf-8', 'cache-control': 'public, max-age=0, s-maxage=60' } });
}
