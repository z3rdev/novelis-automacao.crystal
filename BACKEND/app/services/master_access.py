"""One shared master policy; short grants remain local to each operator session."""
import hashlib
import hmac
import secrets
import threading
import time
from datetime import UTC, datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS hub_master_policy (
    id INTEGER PRIMARY KEY CHECK(id=1), salt TEXT NOT NULL, digest TEXT NOT NULL,
    rounds INTEGER NOT NULL, revision TEXT NOT NULL, updated_at TEXT NOT NULL,
    updated_by TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS hub_master_attempts (
    actor TEXT PRIMARY KEY, failures INTEGER NOT NULL, locked_until REAL NOT NULL);
"""
ROUNDS = 600_000
GRANT_SECONDS = 15 * 60


class MasterDenied(PermissionError):
    pass


class MasterAccess:
    def __init__(self, store, clock=time.time):
        self.store, self.clock = store, clock
        self._grants = {}
        self._lock = threading.RLock()

    def _policy(self):
        with self.store.connection() as db:
            db.executescript(SCHEMA)
            return db.execute("SELECT salt,digest,rounds,revision FROM hub_master_policy WHERE id=1").fetchone()

    def status(self, actor: dict, *, can_setup=False):
        policy = self._policy()
        with self._lock:
            expiry, revision = self._grants.get(actor["id"], (0, None))
            unlocked = bool(policy and revision == policy[3] and expiry > self.clock())
            if not unlocked:
                self._grants.pop(actor["id"], None)
        return {"configured": bool(policy), "can_setup": bool(can_setup and not policy),
                "unlocked": unlocked,
                "expires_at": datetime.fromtimestamp(expiry, UTC).isoformat() if unlocked else None}

    @staticmethod
    def _derive(password, salt, rounds):
        return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), rounds).hex()

    def policy_state(self):
        with self.store.connection() as db:
            db.executescript(SCHEMA)
            row = db.execute("SELECT updated_at,updated_by FROM hub_master_policy WHERE id=1").fetchone()
        return {"configured": bool(row), "updated_at": row[0] if row else None,
                "updated_by": row[1] if row else None}

    def save_policy(self, password: str, actor: dict, *, can_manage=False):
        if not can_manage:
            raise MasterDenied("Modo desenvolvedor desativado.")
        if not 8 <= len(password) <= 256:
            raise ValueError("Use entre 8 e 256 caracteres.")
        salt, revision = secrets.token_hex(16), secrets.token_hex(16)
        digest = self._derive(password, salt, ROUNDS)
        with self.store.connection() as db:
            db.executescript(SCHEMA)
            db.execute("INSERT INTO hub_master_policy VALUES (1,?,?,?,?,?,?) ON CONFLICT(id) "
                "DO UPDATE SET salt=excluded.salt,digest=excluded.digest,rounds=excluded.rounds,"
                "revision=excluded.revision,updated_at=excluded.updated_at,updated_by=excluded.updated_by",
                (salt, digest, ROUNDS, revision, datetime.now(UTC).isoformat(), actor["windows_user"]))
            db.execute("DELETE FROM hub_master_attempts")
        with self._lock:
            self._grants.clear()
        return self.policy_state()

    def setup(self, password: str, actor: dict, *, can_setup=False):
        if not can_setup:
            raise MasterDenied("O cadastro inicial deve ser feito no computador do desenvolvedor.")
        if not 8 <= len(password) <= 256:
            raise ValueError("Use uma senha mestre entre 8 e 256 caracteres.")
        salt, revision = secrets.token_hex(16), secrets.token_hex(16)
        digest = self._derive(password, salt, ROUNDS)
        with self.store.connection() as db:
            db.executescript(SCHEMA)
            if db.execute("SELECT 1 FROM hub_master_policy WHERE id=1").fetchone():
                raise MasterDenied("A senha mestre já foi cadastrada. Desbloqueie com a senha existente.")
            db.execute("INSERT INTO hub_master_policy VALUES (1,?,?,?,?,?,?)", (
                salt, digest, ROUNDS, revision, datetime.now(UTC).isoformat(), actor["windows_user"]))
        with self._lock:
            self._grants[actor["id"]] = (self.clock() + GRANT_SECONDS, revision)
        return self.status(actor)

    def unlock(self, password: str, actor: dict):
        policy = self._policy()
        if not policy:
            raise MasterDenied("A senha mestre ainda não foi cadastrada pelo responsável.")
        identity = f"{actor['windows_user'].casefold()}|{actor['computer_name'].casefold()}"
        # Check and update in a shared transaction to bound attempts across computers.
        with self.store.connection() as db:
            row = db.execute("SELECT failures,locked_until FROM hub_master_attempts WHERE actor=?", (identity,)).fetchone()
            failures, until = row or (0, 0)
            if until > self.clock():
                raise MasterDenied("Muitas tentativas. Aguarde um minuto antes de tentar novamente.")
            if until:
                failures = 0
            correct = len(password) <= 256 and hmac.compare_digest(self._derive(password, policy[0], policy[2]), policy[1])
            if correct:
                db.execute("DELETE FROM hub_master_attempts WHERE actor=?", (identity,))
            else:
                failures += 1
                db.execute("INSERT INTO hub_master_attempts VALUES (?,?,?) ON CONFLICT(actor) "
                    "DO UPDATE SET failures=excluded.failures,locked_until=excluded.locked_until",
                    (identity, failures, self.clock() + 60 if failures >= 5 else 0))
        if not correct:
            raise MasterDenied("Senha mestre incorreta.")
        with self._lock:
            self._grants[actor["id"]] = (self.clock() + GRANT_SECONDS, policy[3])
        return self.status(actor)

    def require(self, actor):
        if not self.status(actor)["unlocked"]:
            raise MasterDenied("Desbloqueie as configurações com a senha mestre.")

    def lock(self, actor):
        with self._lock:
            self._grants.pop(actor["id"], None)
