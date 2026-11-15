SCHEMA = """
CREATE TABLE IF NOT EXISTS public.cargo_hub_chat_people (
 user_key text PRIMARY KEY, windows_user text NOT NULL, name text NOT NULL,
 sector text, device text NOT NULL, seen_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.cargo_hub_chat_rooms (
 id uuid PRIMARY KEY, room_key text NOT NULL UNIQUE, target_type text NOT NULL,
 target text NOT NULL, creator text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.cargo_hub_chat_documents (
 cte text PRIMARY KEY, guia jsonb, comprovante jsonb, combined jsonb,
 generation uuid, publish_state text NOT NULL DEFAULT 'ready', updated_at timestamptz NOT NULL DEFAULT now());
CREATE TABLE IF NOT EXISTS public.cargo_hub_chat_requests (
 id uuid PRIMARY KEY, room_id uuid NOT NULL REFERENCES public.cargo_hub_chat_rooms(id),
 cte text NOT NULL REFERENCES public.cargo_hub_chat_documents(cte), note text NOT NULL,
 chamado text NOT NULL, requested_by text NOT NULL, requested_name text NOT NULL,
 assigned_to text, assigned_name text, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(room_id,cte));
CREATE TABLE IF NOT EXISTS public.cargo_hub_chat_messages (
 seq bigserial PRIMARY KEY, id uuid NOT NULL UNIQUE,
 room_id uuid NOT NULL REFERENCES public.cargo_hub_chat_rooms(id),
 sender text NOT NULL, sender_name text NOT NULL, client_id uuid NOT NULL,
 body text NOT NULL, kind text NOT NULL, request_id uuid REFERENCES public.cargo_hub_chat_requests(id),
 created_at timestamptz NOT NULL DEFAULT now(), UNIQUE(sender,client_id));
CREATE TABLE IF NOT EXISTS public.cargo_hub_chat_reads (
 room_id uuid NOT NULL REFERENCES public.cargo_hub_chat_rooms(id), user_key text NOT NULL,
 through bigint NOT NULL DEFAULT 0, PRIMARY KEY(room_id,user_key));
CREATE INDEX IF NOT EXISTS ix_chat_messages_room ON public.cargo_hub_chat_messages(room_id,seq DESC);
CREATE INDEX IF NOT EXISTS ix_chat_rooms_target ON public.cargo_hub_chat_rooms(target_type,target);
ALTER TABLE public.cargo_hub_chat_documents ADD COLUMN IF NOT EXISTS archive_id uuid;
ALTER TABLE public.cargo_hub_chat_documents ADD COLUMN IF NOT EXISTS archive_state text NOT NULL DEFAULT 'active';
ALTER TABLE public.cargo_hub_chat_documents ADD COLUMN IF NOT EXISTS ticket_number text;
ALTER TABLE public.cargo_hub_chat_documents ADD COLUMN IF NOT EXISTS confirmed_at timestamptz;
ALTER TABLE public.cargo_hub_chat_documents ADD COLUMN IF NOT EXISTS expires_at timestamptz;
"""

ACCESS = "(r.creator=%s OR (r.target_type='operator' AND r.target=%s) OR (r.target_type='sector' AND r.target=%s))"


def access_params(actor):
    return actor["key"], actor["key"], actor.get("sector") or ""
