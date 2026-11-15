"""Shared tariff history and one lease coordinating collectors across computers."""

from datetime import UTC, datetime
from uuid import uuid4

from app.infrastructure.chamados_postgres import ChamadosPostgres, CommunicationUnavailable

SCHEMA = """
CREATE TABLE IF NOT EXISTS public.cargo_hub_tarifa_cidades (
 portal_id text PRIMARY KEY, ibge integer, uf text NOT NULL, nome text NOT NULL,
 label text NOT NULL, portal_label text NOT NULL, search_text text NOT NULL, matched boolean NOT NULL);
CREATE TABLE IF NOT EXISTS public.cargo_hub_tarifas (
 id text PRIMARY KEY, origem_id text NOT NULL, destino_id text NOT NULL, veiculo text NOT NULL,
 inicio date, fim date, valid boolean NOT NULL, search_text text NOT NULL,
 payload jsonb NOT NULL, hash text NOT NULL, listed boolean NOT NULL DEFAULT true,
 first_seen timestamptz NOT NULL DEFAULT now(), last_seen timestamptz NOT NULL DEFAULT now());
CREATE INDEX IF NOT EXISTS ix_tarifa_route ON public.cargo_hub_tarifas(origem_id,destino_id);
CREATE INDEX IF NOT EXISTS ix_tarifa_validity ON public.cargo_hub_tarifas(fim,inicio);
CREATE TABLE IF NOT EXISTS public.cargo_hub_tarifa_versions (
 id text NOT NULL, hash text NOT NULL, payload jsonb NOT NULL, observed_at timestamptz NOT NULL DEFAULT now(),
 PRIMARY KEY(id,hash));
CREATE TABLE IF NOT EXISTS public.cargo_hub_tarifa_sync (
 id integer PRIMARY KEY CHECK(id=1), state text NOT NULL DEFAULT 'idle', lease text,
 lease_until timestamptz, started_at timestamptz, completed_at timestamptz, next_check_at timestamptz,
 last_attempt timestamptz, message text NOT NULL DEFAULT '', total integer NOT NULL DEFAULT 0,
 cities integer NOT NULL DEFAULT 0, unmatched integer NOT NULL DEFAULT 0);
INSERT INTO public.cargo_hub_tarifa_sync(id) VALUES(1) ON CONFLICT DO NOTHING;
ALTER TABLE public.cargo_hub_tarifa_sync ADD COLUMN IF NOT EXISTS stage text NOT NULL DEFAULT '';
ALTER TABLE public.cargo_hub_tarifa_sync ADD COLUMN IF NOT EXISTS error_code text NOT NULL DEFAULT '';
"""
VALIDITY = "CASE WHEN NOT valid THEN 'inconsistente' WHEN inicio>%(today)s THEN 'futura' WHEN fim<%(today)s THEN 'vencida' ELSE 'vigente' END"


class TariffsPostgres:
    def __init__(self, config):
        self.db = ChamadosPostgres(config)

    @property
    def enabled(self):
        return self.db.enabled

    def initialize(self):
        with self.db.connection() as db:
            db.execute(SCHEMA)

    def sync_status(self):
        with self.db.connection() as db:
            value = dict(
                db.execute("SELECT * FROM public.cargo_hub_tarifa_sync WHERE id=1").fetchone()
            )
        if (
            value["state"] == "running"
            and value["lease_until"]
            and value["lease_until"] < datetime.now(UTC)
        ):
            value["state"] = "interrupted"
            value["message"] = "A coleta anterior foi interrompida; aguardando uma nova tentativa."
        return {
            key: item.isoformat() if isinstance(item, datetime) else item
            for key, item in value.items()
            if key not in {"lease", "lease_until"}
        }

    def claim(self, force=False):
        lease = str(uuid4())
        with self.db.connection() as db:
            value = db.execute(
                """UPDATE public.cargo_hub_tarifa_sync
                SET lease=%s,lease_until=now()+interval '15 minutes',state='running',started_at=now(),last_attempt=now(),stage='consulta_portal',error_code='',message='Consultando tarifário Novelis.'
                WHERE id=1 AND (lease_until IS NULL OR lease_until<now())
                AND (last_attempt IS NULL OR last_attempt<now()-interval '60 seconds')
                AND (%s OR next_check_at IS NULL OR next_check_at<=now()) RETURNING id""",
                (lease, force),
            ).fetchone()
        return lease if value else None

    def progress(self, lease, stage):
        with self.db.connection() as db:
            db.execute(
                "UPDATE public.cargo_hub_tarifa_sync SET stage=%s WHERE id=1 AND lease=%s",
                (stage, lease),
            )

    def fail(self, lease, message, *, stage="", code=""):
        with self.db.connection() as db:
            db.execute(
                """UPDATE public.cargo_hub_tarifa_sync SET state='failed',message=%s,
                next_check_at=now()+interval '15 minutes',lease=NULL,lease_until=NULL,stage=%s,error_code=%s WHERE id=1 AND lease=%s""",
                (message, stage, code, lease),
            )

    def save(self, rows, cities, next_check, lease):
        from psycopg.types.json import Jsonb

        from app.services.tariffs.models import fingerprint
        from app.services.tariffs.municipalities import normalized

        with self.db.connection() as db:
            # COPY includes client transfer time. The shared connection's 10s
            # query budget is too short for the complete remote tariff catalog.
            # Keep the larger budget local to this transaction; lock_timeout
            # and ordinary reads retain their existing limits.
            db.execute("SET LOCAL statement_timeout = '120s'")
            current = db.execute(
                "SELECT lease,total FROM public.cargo_hub_tarifa_sync WHERE id=1 FOR UPDATE"
            ).fetchone()
            if current["lease"] != lease:
                raise CommunicationUnavailable("Outra coleta assumiu a sincronização do tarifário.")
            if not rows and current["total"]:
                raise CommunicationUnavailable(
                    "O portal retornou uma lista vazia. O catálogo anterior foi preservado."
                )
            db.execute(
                "CREATE TEMP TABLE tariff_cities (LIKE public.cargo_hub_tarifa_cidades INCLUDING DEFAULTS) ON COMMIT DROP"
            )
            db.execute(
                "CREATE TEMP TABLE tariff_import (LIKE public.cargo_hub_tarifas INCLUDING DEFAULTS) ON COMMIT DROP"
            )
            with db.cursor() as cursor:
                with cursor.copy(
                    "COPY tariff_cities(portal_id,ibge,uf,nome,label,portal_label,search_text,matched) FROM STDIN"
                ) as copy:
                    for value in cities:
                        copy.write_row(
                            [
                                value[key]
                                for key in (
                                    "portal_id",
                                    "ibge",
                                    "uf",
                                    "nome",
                                    "label",
                                    "portal_label",
                                )
                            ]
                            + [normalized(value["label"]), value["matched"]]
                        )
                with cursor.copy(
                    "COPY tariff_import(id,origem_id,destino_id,veiculo,inicio,fim,valid,search_text,payload,hash) FROM STDIN"
                ) as copy:
                    for row in {row["id"]: row for row in rows}.values():
                        copy.write_row(
                            [
                                row["id"],
                                row["origemId"],
                                row["destinoId"],
                                row["veiculo"],
                                row["inicio"],
                                row["fim"],
                                row["vigenciaValida"],
                                normalized(" ".join(str(v or "") for v in row.values())),
                                Jsonb(row),
                                fingerprint(row),
                            ]
                        )
            db.execute("""INSERT INTO public.cargo_hub_tarifa_cidades SELECT * FROM tariff_cities
                ON CONFLICT(portal_id) DO UPDATE SET ibge=excluded.ibge,uf=excluded.uf,nome=excluded.nome,label=excluded.label,
                portal_label=excluded.portal_label,search_text=excluded.search_text,matched=excluded.matched
                WHERE (cargo_hub_tarifa_cidades.ibge,cargo_hub_tarifa_cidades.label,cargo_hub_tarifa_cidades.portal_label,cargo_hub_tarifa_cidades.matched)
                IS DISTINCT FROM (excluded.ibge,excluded.label,excluded.portal_label,excluded.matched)""")
            db.execute("""INSERT INTO public.cargo_hub_tarifa_versions(id,hash,payload)
                SELECT id,hash,payload FROM tariff_import ON CONFLICT DO NOTHING""")
            db.execute(
                "UPDATE public.cargo_hub_tarifas SET listed=false WHERE listed AND id NOT IN (SELECT id FROM tariff_import)"
            )
            db.execute("""INSERT INTO public.cargo_hub_tarifas SELECT * FROM tariff_import
                ON CONFLICT(id) DO UPDATE SET origem_id=excluded.origem_id,destino_id=excluded.destino_id,veiculo=excluded.veiculo,
                inicio=excluded.inicio,fim=excluded.fim,valid=excluded.valid,search_text=excluded.search_text,
                payload=excluded.payload,hash=excluded.hash,listed=true,last_seen=now()
                WHERE cargo_hub_tarifas.hash IS DISTINCT FROM excluded.hash OR NOT cargo_hub_tarifas.listed""")
            db.execute(
                """UPDATE public.cargo_hub_tarifa_sync SET state='completed',completed_at=now(),next_check_at=%s,
                total=%s,cities=%s,unmatched=%s,message='Catálogo atualizado.',stage='concluida',error_code='',lease=NULL,lease_until=NULL WHERE id=1 AND lease=%s""",
                (next_check, len(rows), len(cities), sum(not v["matched"] for v in cities), lease),
            )

    def page(
        self,
        *,
        today,
        search="",
        origin="",
        destination="",
        vehicle="",
        validity="vigente",
        page=0,
        size=50,
    ):
        from app.services.tariffs.municipalities import normalized

        params = {
            "today": today,
            "search": "%" + normalized(search) + "%",
            "origin": origin,
            "destination": destination,
            "vehicle": vehicle,
            "validity": validity,
            "size": min(100, max(1, size)),
        }
        conditions = ["search_text LIKE %(search)s"]
        for name, column in (
            ("origin", "origem_id"),
            ("destination", "destino_id"),
            ("vehicle", "veiculo"),
        ):
            if params[name]:
                conditions.append(f"{column}=%({name})s")
        base = " AND ".join(conditions)
        where = base + (" AND (" + VALIDITY + ")=%(validity)s" if validity != "todos" else "")
        with self.db.connection() as db:
            counts = db.execute(
                "SELECT "
                + VALIDITY
                + " AS status,count(*) AS total FROM public.cargo_hub_tarifas WHERE "
                + base
                + " GROUP BY 1",
                params,
            ).fetchall()
            total = db.execute(
                "SELECT count(*) AS total FROM public.cargo_hub_tarifas WHERE " + where, params
            ).fetchone()["total"]
            page = min(max(0, page), max(0, (total - 1) // params["size"]))
            params["offset"] = page * params["size"]
            rows = db.execute(
                "SELECT payload,listed,"
                + VALIDITY
                + " AS status,CASE WHEN listed THEN (SELECT completed_at FROM public.cargo_hub_tarifa_sync WHERE id=1) ELSE last_seen END AS last_seen FROM public.cargo_hub_tarifas WHERE "
                + where
                + " ORDER BY inicio DESC NULLS LAST,id LIMIT %(size)s OFFSET %(offset)s",
                params,
            ).fetchall()
            vehicles = db.execute(
                "SELECT DISTINCT veiculo FROM public.cargo_hub_tarifas ORDER BY veiculo"
            ).fetchall()
        return {
            "rows": [
                {
                    **row["payload"],
                    "status": row["status"],
                    "presentePortal": row["listed"],
                    "conferidoEm": row["last_seen"].isoformat(),
                }
                for row in rows
            ],
            "total": total,
            "page": page,
            "page_size": params["size"],
            "counts": {r["status"]: r["total"] for r in counts},
            "vehicles": [r["veiculo"] for r in vehicles],
        }

    def cities(self, search=""):
        from app.services.tariffs.municipalities import normalized

        with self.db.connection() as db:
            return db.execute(
                "SELECT portal_id,ibge,label,portal_label,matched FROM public.cargo_hub_tarifa_cidades WHERE search_text LIKE %s ORDER BY label LIMIT 60",
                ("%" + normalized(search) + "%",),
            ).fetchall()

    def audit_snapshot(self, routes, first, last):
        with self.db.connection() as db:
            rows = db.execute(
                "SELECT payload FROM public.cargo_hub_tarifas WHERE listed AND valid "
                "AND (payload->>'origem')=ANY(%s) AND (payload->>'destino')=ANY(%s) "
                "AND inicio<=%s AND (fim IS NULL OR fim>=%s)",
                ([v[0] for v in routes], [v[1] for v in routes], last, first),
            ).fetchall()
            meta = db.execute(
                "SELECT state,completed_at FROM public.cargo_hub_tarifa_sync WHERE id=1"
            ).fetchone()
        return [row["payload"] for row in rows], {
            "state": meta["state"],
            "completed_at": meta["completed_at"].isoformat() if meta["completed_at"] else None,
        }

    def detail(self, identifier):
        with self.db.connection() as db:
            value = db.execute(
                "SELECT payload,listed,CASE WHEN listed THEN (SELECT completed_at FROM public.cargo_hub_tarifa_sync WHERE id=1) ELSE last_seen END AS last_seen FROM public.cargo_hub_tarifas WHERE id=%s",
                (identifier,),
            ).fetchone()
        return (
            {
                **value["payload"],
                "presentePortal": value["listed"],
                "conferidoEm": value["last_seen"].isoformat(),
            }
            if value
            else None
        )
