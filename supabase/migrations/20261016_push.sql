-- Daily-song push: one row per browser subscription. Run once in the Supabase SQL editor (or `supabase db push`).
create table if not exists public.musicy_push (
  id bigint generated always as identity primary key,
  uid text not null,
  lang text not null default 'he',
  endpoint text not null unique,
  p256dh text not null,
  auth text not null,
  created_at timestamptz not null default now(),
  last_sent date
);
alter table public.musicy_push enable row level security;
drop policy if exists "musicy_push_insert" on public.musicy_push;
create policy "musicy_push_insert" on public.musicy_push for insert to anon with check (char_length(endpoint) < 600 and char_length(uid) <= 20);
drop policy if exists "musicy_push_delete_own" on public.musicy_push;
create policy "musicy_push_delete_own" on public.musicy_push for delete to anon using (true);
-- the sender runs as service role (edge function), so no select for anon.
-- schedule (Supabase Dashboard → Edge Functions → daily-push → Cron, or pg_cron): every day 16:00 UTC = 19:00 Israel (18:00 in winter — use 17:00 UTC then)
-- select cron.schedule('musicy-daily-push', '0 16 * * *', $$ select net.http_post(url := 'https://ludpwcctxblpdqnijgyq.supabase.co/functions/v1/daily-push', headers := '{"Authorization":"Bearer <SERVICE_ROLE_KEY>"}'::jsonb) $$);
