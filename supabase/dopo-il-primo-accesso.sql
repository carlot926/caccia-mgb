-- Da eseguire UNA volta, subito DOPO il tuo primo accesso al sito con Google.
-- Rende amministratore il primo utente registrato (cioè tu) e ti riporta nome e voti.
with me as (select id from auth.users order by created_at limit 1)
insert into public.admins (user_id) select id from me on conflict do nothing;

with me as (select id from auth.users order by created_at limit 1)
insert into public.profiles (id, nome) select id, 'Carlo' from me
on conflict (id) do update set nome = excluded.nome;

with me as (select id from auth.users order by created_at limit 1),
v(auto_id, colore, interni, cerchi) as (values
  ('as24-19ca2321-e765-48dc-b21a-bb683f31c9e2', 4, 3, 3),
  ('as24-59ec2229-8734-4ee0-a4be-f3cc1d5a3895', 4, 5, 5),
  ('u1kap3b3', 4, 5, 5),
  ('u1ygiogo', 5, 5, 5),
  ('u1yxkyk8', 3, 4, 5)
)
insert into public.voti (user_id, auto_id, colore, interni, cerchi)
select me.id, v.auto_id, v.colore, v.interni, v.cerchi from me, v
on conflict (user_id, auto_id) do update set colore = excluded.colore, interni = excluded.interni, cerchi = excluded.cerchi;
