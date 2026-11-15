"""Private PostgreSQL mailbox: typed requests, one lease per target backend."""

from datetime import datetime
from threading import Lock
from uuid import uuid4

from app.infrastructure.chamados_postgres import ChamadosPostgres, CommunicationUnavailable

SCHEMA = """
CREATE TABLE IF NOT EXISTS public.cargo_hub_diagnostic_agents (
 device_id text PRIMARY KEY, instance_id text NOT NULL, machine_id text NOT NULL,
 computer_name text NOT NULL, version text NOT NULL, installation_kind text NOT NULL,
 protocol integer NOT NULL, last_seen timestamptz NOT NULL DEFAULT now(),
 online boolean NOT NULL DEFAULT true, current_request text);
CREATE TABLE IF NOT EXISTS public.cargo_hub_diagnostic_requests (
 id text PRIMARY KEY, device_id text NOT NULL, computer_name text NOT NULL,
 requested_by text NOT NULL, requested_at timestamptz NOT NULL DEFAULT now(),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '10 minutes',
 state text NOT NULL DEFAULT 'queued', options jsonb NOT NULL,
 claimed_by text, lease_until timestamptz, started_at timestamptz, finished_at timestamptz,
 result jsonb, error_code text NOT NULL DEFAULT '');
CREATE INDEX IF NOT EXISTS ix_diagnostic_target ON public.cargo_hub_diagnostic_requests(device_id,state,requested_at);
"""
FIELDS = "id,device_id,computer_name,requested_by,requested_at,expires_at,state,options,started_at,finished_at,error_code"


class DiagnosticTargetUnavailable(CommunicationUnavailable):
    pass


def serialize(row):
    return {
        key: value.isoformat() if isinstance(value, datetime) else value
        for key, value in dict(row).items()
    }


class DiagnosticQueue:
    def __init__(self, config):
        self.db = ChamadosPostgres(config)
        self.ready, self.lock = False, Lock()

    @property
    def enabled(self):
        return self.db.enabled

    def ensure(self):
        if not self.enabled:
            raise CommunicationUnavailable(
                "Configure o banco de comunicação para o diagnóstico remoto."
            )
        with self.lock:
            if not self.ready:
                with self.db.connection() as db:
                    db.execute(SCHEMA)
                self.ready = True

    @staticmethod
    def expire(db):
        db.execute("""UPDATE public.cargo_hub_diagnostic_requests SET
            state=CASE WHEN state='queued' THEN 'expired' ELSE 'timed_out' END,
            error_code=CASE WHEN state='queued' THEN 'client_unavailable' ELSE 'lease_expired' END,
            finished_at=now() WHERE (state='queued' AND expires_at<=now())
            OR (state='running' AND lease_until<=now())""")

    def heartbeat(self, device, instance, current=None):
        self.ensure()
        with self.db.connection() as db:
            db.execute(
                """INSERT INTO public.cargo_hub_diagnostic_agents
                (device_id,instance_id,machine_id,computer_name,version,installation_kind,protocol,current_request)
                VALUES(%s,%s,%s,%s,%s,%s,1,%s) ON CONFLICT(device_id) DO UPDATE SET
                instance_id=excluded.instance_id,machine_id=excluded.machine_id,computer_name=excluded.computer_name,
                version=excluded.version,installation_kind=excluded.installation_kind,
                protocol=1,last_seen=now(),online=true,current_request=excluded.current_request""",
                (
                    device["id"],
                    instance,
                    device["machine_id"],
                    device["computer_name"],
                    device["version"],
                    device["installation_kind"],
                    current,
                ),
            )

    def leave(self, device_id, instance):
        if self.ready:
            with self.db.connection() as db:
                db.execute(
                    "UPDATE public.cargo_hub_diagnostic_agents SET online=false,current_request=NULL WHERE device_id=%s AND instance_id=%s",
                    (device_id, instance),
                )

    def agents(self):
        self.ensure()
        with self.db.connection() as db:
            rows = db.execute("""SELECT device_id,machine_id,computer_name,version,installation_kind,protocol,
                last_seen,current_request,(online AND last_seen>now()-interval '90 seconds') AS online
                FROM public.cargo_hub_diagnostic_agents ORDER BY computer_name,installation_kind LIMIT 1000""").fetchall()
        return [serialize(row) for row in rows]

    def create(self, device_id, actor, options):
        from psycopg.types.json import Jsonb

        self.ensure()
        with self.db.connection() as db:
            self.expire(db)
            agent = db.execute(
                """SELECT computer_name FROM public.cargo_hub_diagnostic_agents
                WHERE device_id=%s AND protocol=1 AND online AND last_seen>now()-interval '90 seconds'
                FOR UPDATE""",
                (device_id,),
            ).fetchone()
            if not agent:
                raise DiagnosticTargetUnavailable(
                    "Computador offline ou sem o agente de diagnóstico atualizado."
                )
            existing = db.execute(
                f"SELECT {FIELDS} FROM public.cargo_hub_diagnostic_requests WHERE device_id=%s AND state IN ('queued','running') ORDER BY requested_at LIMIT 1",
                (device_id,),
            ).fetchone()
            if existing:
                return serialize(existing)
            row = db.execute(
                f"""INSERT INTO public.cargo_hub_diagnostic_requests
                (id,device_id,computer_name,requested_by,options) VALUES(%s,%s,%s,%s,%s) RETURNING {FIELDS}""",
                (str(uuid4()), device_id, agent["computer_name"], actor, Jsonb(options)),
            ).fetchone()
        return serialize(row)

    def claim(self, device_id, instance):
        self.ensure()
        with self.db.connection() as db:
            self.expire(db)
            row = db.execute(
                """SELECT id,options FROM public.cargo_hub_diagnostic_requests
                WHERE device_id=%s AND state='queued' AND expires_at>now()
                AND EXISTS(SELECT 1 FROM public.cargo_hub_diagnostic_agents
                    WHERE device_id=%s AND instance_id=%s AND online)
                AND NOT EXISTS(SELECT 1 FROM public.cargo_hub_diagnostic_requests
                    WHERE device_id=%s AND state='running')
                ORDER BY requested_at FOR UPDATE SKIP LOCKED LIMIT 1""",
                (device_id, device_id, instance, device_id),
            ).fetchone()
            if not row:
                return None
            db.execute(
                """UPDATE public.cargo_hub_diagnostic_requests SET state='running',claimed_by=%s,
                started_at=now(),lease_until=now()+interval '4 minutes' WHERE id=%s""",
                (instance, row["id"]),
            )
        return serialize(row)

    def finish(self, identifier, instance, result=None, error=""):
        from psycopg.types.json import Jsonb

        with self.db.connection() as db:
            row = db.execute(
                """UPDATE public.cargo_hub_diagnostic_requests SET state=%s,result=%s,
                error_code=%s,finished_at=now(),lease_until=NULL WHERE id=%s AND claimed_by=%s
                AND state='running' AND lease_until>now() RETURNING id""",
                (
                    "failed" if error else "completed",
                    Jsonb(result) if result is not None else None,
                    error,
                    identifier,
                    instance,
                ),
            ).fetchone()
        return bool(row)

    def list(self):
        self.ensure()
        with self.db.connection() as db:
            self.expire(db)
            rows = db.execute(
                f"SELECT {FIELDS},result->'summary' AS summary FROM public.cargo_hub_diagnostic_requests ORDER BY requested_at DESC LIMIT 100"
            ).fetchall()
        return [serialize(row) for row in rows]

    def get(self, identifier):
        self.ensure()
        with self.db.connection() as db:
            self.expire(db)
            row = db.execute(
                f"SELECT {FIELDS},result FROM public.cargo_hub_diagnostic_requests WHERE id=%s",
                (identifier,),
            ).fetchone()
        return serialize(row) if row else None
