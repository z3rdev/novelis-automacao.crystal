"""Allowlisted diagnostic codes; never expose a driver or portal response."""

import re


def portal_code(value):
    return value if value in {"portal", "timeout", "network"} or re.fullmatch(
        r"http_[1-5][0-9]{2}", str(value)
    ) else "portal"


def failure_code(exc, stage):
    if stage == "gravacao":
        cause, seen = exc, set()
        while cause is not None and id(cause) not in seen:
            seen.add(id(cause))
            code = getattr(cause, "sqlstate", None)
            if isinstance(code, str) and re.fullmatch(r"[0-9A-Z]{5}", code):
                return code
            cause = cause.__cause__ or cause.__context__
        return "database"
    return portal_code(getattr(exc, "code", "portal"))


def failure_message(stage, code):
    if stage == "gravacao":
        if code == "57014":
            return "O banco interrompeu a gravação do tarifário por tempo limite (57014)."
        if code == "55P03":
            return "O banco está ocupado; não foi possível obter acesso à gravação (55P03)."
        return "Falha ao gravar a atualização no banco de comunicação."
    if code == "timeout":
        return "O portal excedeu o tempo de resposta após duas tentativas."
    if code == "network":
        return "A conexão com o portal foi interrompida durante a consulta do tarifário."
    if code in {"http_401", "http_403"}:
        return "O portal recusou o acesso ao tarifário. Verifique a conta configurada."
    return "O portal não concluiu a consulta do tarifário."


class TariffRefreshError(RuntimeError):
    def __init__(self, state):
        self.stage = "gravacao" if state.get("stage") == "gravacao" else "consulta_portal"
        self.code = portal_code(state.get("error_code"))
        if self.stage == "gravacao":
            code = str(state.get("error_code") or "")
            self.code = code if re.fullmatch(r"[0-9A-Z]{5}", code) else "database"
        message = failure_message(self.stage, self.code)
        if state.get("state") == "interrupted":
            self.code = "interrupted"
            message = "A sincronização anterior do tarifário foi interrompida."
        super().__init__(message + " O catálogo anterior foi preservado.")
