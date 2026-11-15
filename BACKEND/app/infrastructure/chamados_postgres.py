"""The communication database stores called records, not Rodopar SQL credentials."""
from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256

from app.services.hub_views import chamado_view


class CommunicationUnavailable(RuntimeError):
    pass


class ChamadosPostgres:
    def __init__(self, config):
        self.config = config

    @property
    def enabled(self):
        return bool(self.config and self.config.get("CHAMADOS_PG_HOST"))

    @contextmanager
    def connection(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
            options = dict(host=self.config.get("CHAMADOS_PG_HOST"),
                port=int(self.config.get("CHAMADOS_PG_PORT") or 5432),
                dbname=self.config.get("CHAMADOS_PG_DATABASE"),
                user=self.config.get("CHAMADOS_PG_USER"), password=self.config.get("CHAMADOS_PG_PASS"),
                sslmode=self.config.get("CHAMADOS_PG_SSLMODE") or "require", connect_timeout=5,
                application_name="CargoHub-chamados", options="-c statement_timeout=10000 -c lock_timeout=5000",
                row_factory=dict_row)
            if ca := self.config.get("CHAMADOS_PG_SSLROOTCERT"):
                options["sslrootcert"] = ca
            if options["sslmode"] not in {"disable", "require", "verify-ca", "verify-full"}:
                raise CommunicationUnavailable("Modo SSL inválido para o banco de comunicação (CHAMADOS_PG_SSLMODE).")
            with psycopg.connect(**options) as db:
                yield db
        except CommunicationUnavailable:
            raise
        except (ImportError, ValueError):
            raise CommunicationUnavailable("Configure o driver e o acesso privado ao PostgreSQL de chamados.") from None
        except Exception:
            # Never forward a libpq error, connection string or credentials to API/logs.
            raise CommunicationUnavailable("Banco de comunicação indisponível. Verifique rede, TLS e permissões do PostgreSQL.") from None

    def initialize(self):
        with self.connection() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS public.cargo_hub_chamados (
                id text PRIMARY KEY, cte text NOT NULL, chave text NOT NULL, chamado text NOT NULL,
                andamento text NOT NULL, data_sort text NOT NULL, search_text text NOT NULL,
                payload jsonb NOT NULL, raw_payload jsonb NOT NULL, source_at timestamptz NOT NULL,
                updated_at timestamptz NOT NULL DEFAULT now())""")
            db.execute("CREATE INDEX IF NOT EXISTS ix_chamados_order ON public.cargo_hub_chamados(data_sort DESC,id)")
            db.execute("CREATE INDEX IF NOT EXISTS ix_chamados_state ON public.cargo_hub_chamados(andamento)")
            db.execute("CREATE INDEX IF NOT EXISTS ix_chamados_chave ON public.cargo_hub_chamados(chave)")
            db.execute("CREATE INDEX IF NOT EXISTS ix_chamados_cte ON public.cargo_hub_chamados(cte)")
            db.execute("""CREATE TABLE IF NOT EXISTS public.cargo_hub_chamados_sources (
                id text PRIMARY KEY, fingerprint text NOT NULL, imported_at timestamptz NOT NULL DEFAULT now())""")

    def imported(self, identifier, fingerprint):
        with self.connection() as db:
            row = db.execute("SELECT fingerprint FROM public.cargo_hub_chamados_sources WHERE id=%s", (identifier,)).fetchone()
            return bool(row and row["fingerprint"] == fingerprint)

    @staticmethod
    def values(raw, source_at):
        from psycopg.types.json import Jsonb
        view = chamado_view(raw)
        chave = "".join(ch for ch in str(raw.get("cteId") or "") if ch.isdigit())
        chave = chave if len(chave) == 44 else ""
        identity = f"{chave or view['cte']}|{view['chamado'] or ''}"
        view["id"] = sha256(identity.encode()).hexdigest()
        search = " ".join(str(value or "") for value in view.values()).casefold()
        return (view["id"], view["cte"], chave, view["chamado"] or "", view["andamento"],
                view["data"], search, Jsonb(view), Jsonb(raw), source_at)

    def import_rows(self, rows, identifier, fingerprint, source_at):
        with self.connection() as db:
            # One shared transaction also coordinates importing on several computers.
            db.execute("SELECT pg_advisory_xact_lock(71620351)")
            existing = db.execute("SELECT fingerprint FROM public.cargo_hub_chamados_sources WHERE id=%s", (identifier,)).fetchone()
            if existing and existing["fingerprint"] == fingerprint:
                return 0
            values = {item[0]: item for item in (self.values(raw, source_at) for raw in rows)}
            db.execute("CREATE TEMP TABLE cargo_hub_import (LIKE public.cargo_hub_chamados INCLUDING DEFAULTS) ON COMMIT DROP")
            with db.cursor() as cursor:
                with cursor.copy("""COPY cargo_hub_import
                    (id,cte,chave,chamado,andamento,data_sort,search_text,payload,raw_payload,source_at)
                    FROM STDIN""") as copy:
                    for item in values.values():
                        copy.write_row(item)
                cursor.execute("""INSERT INTO public.cargo_hub_chamados
                    (id,cte,chave,chamado,andamento,data_sort,search_text,payload,raw_payload,source_at)
                    SELECT id,cte,chave,chamado,andamento,data_sort,search_text,payload,raw_payload,source_at FROM cargo_hub_import
                    ON CONFLICT(id) DO UPDATE SET cte=excluded.cte,chave=excluded.chave,
                    chamado=excluded.chamado,andamento=excluded.andamento,data_sort=excluded.data_sort,
                    search_text=excluded.search_text,payload=excluded.payload,raw_payload=excluded.raw_payload,
                    source_at=excluded.source_at,updated_at=now()
                    WHERE public.cargo_hub_chamados.source_at<=excluded.source_at""")
            db.execute("""INSERT INTO public.cargo_hub_chamados_sources(id,fingerprint) VALUES (%s,%s)
                ON CONFLICT(id) DO UPDATE SET fingerprint=excluded.fingerprint,imported_at=now()""", (identifier, fingerprint))
        return len(rows)

    def page(self, *, search="", status="todos", page=0, size=100):
        size, page = min(100, max(1, size)), max(0, page)
        term = search.casefold().strip().replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        where, params = "TRUE", []
        if term:
            where += " AND search_text LIKE %s"
            params.append("%" + term + "%")
        if status != "todos":
            where += " AND andamento=%s"
            params.append(status)
        with self.connection() as db:
            counts = db.execute("SELECT andamento,count(*) AS total FROM public.cargo_hub_chamados GROUP BY andamento").fetchall()
            total = db.execute("SELECT count(*) AS total FROM public.cargo_hub_chamados WHERE " + where, params).fetchone()["total"]
            last_page = max(0, (total - 1) // size)
            page = min(page, last_page)
            rows = db.execute("SELECT payload FROM public.cargo_hub_chamados WHERE " + where +
                " ORDER BY data_sort DESC,id LIMIT %s OFFSET %s", [*params, size, page * size]).fetchall()
            synced = db.execute("SELECT max(imported_at) AS synced FROM public.cargo_hub_chamados_sources").fetchone()["synced"]
        return {"rows": [row["payload"] for row in rows], "total": total, "page": page, "page_size": size,
                "counts": {row["andamento"]: row["total"] for row in counts}, "source": "postgresql",
                "synced_at": synced.isoformat() if synced else None}

    def counts(self):
        with self.connection() as db:
            rows = db.execute("SELECT andamento,count(*) AS total FROM public.cargo_hub_chamados GROUP BY andamento").fetchall()
        return {row["andamento"]: row["total"] for row in rows}

    def all_raw(self):
        with self.connection() as db:
            return [row["raw_payload"] for row in db.execute("SELECT raw_payload FROM public.cargo_hub_chamados").fetchall()]

    def detail(self, identifier):
        with self.connection() as db:
            return db.execute("SELECT id,chave,raw_payload,updated_at FROM public.cargo_hub_chamados WHERE id=%s",
                              (identifier,)).fetchone()

    def opened_identities(self, rows):
        from app.infrastructure.pending_queue import access_key, cte_number
        keys = [access_key(row) for row in rows if access_key(row)]
        numbers = [cte_number(row) for row in rows if cte_number(row)]
        with self.connection() as db:
            return db.execute("SELECT cte,chave AS \"cteId\",chamado FROM public.cargo_hub_chamados "
                "WHERE chamado<>'' AND (chave=ANY(%s) OR cte=ANY(%s))", (keys, numbers)).fetchall()

    def record_processed(self, value):
        raw = {"cte": value["cte"], "cteId": value.get("cteId"), "chamado": value["chamadoNumero"],
               "dataSort": value["processedAt"], "abertoEm": value["processedAt"], "andamento": "Aberto"}
        self.import_rows([raw], "processed:" + value["cte"], value["processedAt"], datetime.now(UTC))
