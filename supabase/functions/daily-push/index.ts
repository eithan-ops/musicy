// Daily-song push sender. Deploy: `supabase functions deploy daily-push --no-verify-jwt`
// Secrets: VAPID_PUBLIC_KEY, VAPID_PRIVATE_KEY (npx web-push generate-vapid-keys), VAPID_SUBJECT (mailto:...), plus the project's SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY (set automatically).
import webpush from 'npm:web-push@3.6.7';
import { createClient } from 'npm:@supabase/supabase-js@2';

Deno.serve(async () => {
  const sb = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!);
  webpush.setVapidDetails(Deno.env.get('VAPID_SUBJECT') || 'mailto:hello@musicy.fun', Deno.env.get('VAPID_PUBLIC_KEY')!, Deno.env.get('VAPID_PRIVATE_KEY')!);
  const today = new Date().toISOString().slice(0, 10);
  const n = Math.round((Date.UTC(+today.slice(0, 4), +today.slice(5, 7) - 1, +today.slice(8, 10)) - Date.UTC(2026, 0, 1)) / 864e5) + 1;
  const { data: subs } = await sb.from('musicy_push').select('id,endpoint,p256dh,auth,lang,last_sent').or(`last_sent.is.null,last_sent.lt.${today}`).limit(5000);
  let sent = 0, gone = 0;
  for (const s of subs || []) {
    const body = JSON.stringify(s.lang === 'en'
      ? { title: `Musicy · Song of the day #${n}`, body: 'Same song for everyone today. Can you put the band back faster?', url: 'https://musicy.fun/?daily=1' }
      : { title: `Musicy · שיר היום #${n}`, body: 'אותו שיר לכל הארץ. תצליחו להחזיר את הלהקה מהר יותר?', url: 'https://musicy.fun/?daily=1' });
    try { await webpush.sendNotification({ endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth } }, body, { TTL: 6 * 3600 }); sent++;
      await sb.from('musicy_push').update({ last_sent: today }).eq('id', s.id); }
    catch (e) { const code = (e as { statusCode?: number }).statusCode; if (code === 404 || code === 410) { gone++; await sb.from('musicy_push').delete().eq('id', s.id); } }
  }
  return new Response(JSON.stringify({ sent, gone, n }), { headers: { 'content-type': 'application/json' } });
});
