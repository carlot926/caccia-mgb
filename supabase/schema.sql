-- Caccia alla MGB: schema del database.
-- Da incollare una volta in Supabase > SQL Editor > New query > Run.

-- Chi può aggiungere e togliere auto e approvare le proposte.
create table if not exists public.admins (
  user_id uuid primary key references auth.users(id) on delete cascade
);

create or replace function public.is_admin() returns boolean
language sql stable security definer set search_path = public as $$
  select exists (select 1 from public.admins where user_id = auth.uid());
$$;

-- Nome scelto da ciascun giudice.
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  nome text not null check (char_length(nome) between 1 and 40),
  aggiornato timestamptz not null default now()
);

-- Le auto in concorso. "dati" contiene titolo, prezzo, anno, foto, verdetto...
create table if not exists public.preferiti (
  id text primary key check (id ~ '^[A-Za-z0-9_-]{1,120}$'),
  dati jsonb not null,
  salvato_il timestamptz not null default now()
);

-- Un voto per giudice e per auto.
create table if not exists public.voti (
  user_id uuid not null references auth.users(id) on delete cascade,
  auto_id text not null references public.preferiti(id) on delete cascade,
  colore smallint check (colore between 1 and 5),
  interni smallint check (interni between 1 and 5),
  cerchi smallint check (cerchi between 1 and 5),
  aggiornato timestamptz not null default now(),
  primary key (user_id, auto_id)
);

-- Auto proposte dagli amici, in attesa di approvazione.
create table if not exists public.proposte (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null default auth.uid() references auth.users(id) on delete cascade,
  url text not null check (url ~ '^https://' and char_length(url) < 600),
  titolo text check (char_length(titolo) < 200),
  prezzo integer check (prezzo between 0 and 10000000),
  anno smallint check (anno between 1945 and 1990),
  paese text check (char_length(paese) < 40),
  perche text check (char_length(perche) < 1000),
  stato text not null default 'attesa' check (stato in ('attesa', 'approvata', 'scartata')),
  creata timestamptz not null default now()
);

alter table public.admins enable row level security;
alter table public.profiles enable row level security;
alter table public.preferiti enable row level security;
alter table public.voti enable row level security;
alter table public.proposte enable row level security;

-- admins: ognuno vede solo se stesso
drop policy if exists "admins_self" on public.admins;
create policy "admins_self" on public.admins for select using (user_id = auth.uid());

-- profiles: tutti leggono, ognuno scrive il proprio
drop policy if exists "profiles_read" on public.profiles;
create policy "profiles_read" on public.profiles for select using (true);
drop policy if exists "profiles_insert" on public.profiles;
create policy "profiles_insert" on public.profiles for insert with check (id = auth.uid());
drop policy if exists "profiles_update" on public.profiles;
create policy "profiles_update" on public.profiles for update using (id = auth.uid()) with check (id = auth.uid());

-- preferiti: tutti leggono, solo l'admin modifica
drop policy if exists "preferiti_read" on public.preferiti;
create policy "preferiti_read" on public.preferiti for select using (true);
drop policy if exists "preferiti_admin" on public.preferiti;
create policy "preferiti_admin" on public.preferiti for all using (public.is_admin()) with check (public.is_admin());

-- voti: tutti leggono, ognuno scrive i propri
drop policy if exists "voti_read" on public.voti;
create policy "voti_read" on public.voti for select using (true);
drop policy if exists "voti_insert" on public.voti;
create policy "voti_insert" on public.voti for insert with check (user_id = auth.uid());
drop policy if exists "voti_update" on public.voti;
create policy "voti_update" on public.voti for update using (user_id = auth.uid()) with check (user_id = auth.uid());
drop policy if exists "voti_delete" on public.voti;
create policy "voti_delete" on public.voti for delete using (user_id = auth.uid());

-- proposte: chi è registrato propone, vede le proprie; l'admin vede e decide tutto
drop policy if exists "proposte_insert" on public.proposte;
create policy "proposte_insert" on public.proposte for insert to authenticated with check (user_id = auth.uid() and stato = 'attesa');
drop policy if exists "proposte_read" on public.proposte;
create policy "proposte_read" on public.proposte for select using (user_id = auth.uid() or public.is_admin());
drop policy if exists "proposte_admin" on public.proposte;
create policy "proposte_admin" on public.proposte for update using (public.is_admin()) with check (public.is_admin());
drop policy if exists "proposte_admin_del" on public.proposte;
create policy "proposte_admin_del" on public.proposte for delete using (public.is_admin());

grant select on public.profiles, public.preferiti, public.voti to anon, authenticated;
grant insert, update on public.profiles to authenticated;
grant insert, update, delete on public.voti, public.preferiti to authenticated;
grant select, insert, update, delete on public.proposte to authenticated;
grant select on public.admins to authenticated;

-- aggiornamenti in tempo reale
do $$ begin
  begin alter publication supabase_realtime add table public.voti; exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.preferiti; exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.profiles; exception when duplicate_object then null; end;
  begin alter publication supabase_realtime add table public.proposte; exception when duplicate_object then null; end;
end $$;
