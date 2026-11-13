import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def health(self) -> dict[str, Any]:
        return self._request("GET", "/health", timeout=5)

    def current_run(self) -> dict[str, Any]:
        return self._request("GET", "/runs/current", timeout=5)

    def start_automation(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/runs/start",
            {"flow": "pendentes", "dry_run": False},
            timeout=10,
        )

    def start_consulta(self) -> dict[str, Any]:
        return self._request(
            "POST",
            "/runs/start",
            {"flow": "consulta-pendentes", "dry_run": False},
            timeout=10,
        )

    def stop_automation(self) -> dict[str, Any]:
        return self._request("POST", "/runs/stop", timeout=10)

    def chamados(self) -> dict[str, Any]:
        return self._request("GET", "/chamados", timeout=20)

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        timeout: int = 10,
    ) -> dict[str, Any]:
        body = None
        headers = {"Content-Type": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
        request = Request(f"{self.base_url}{path}", data=body, headers=headers, method=method)
        try:
            with urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise ApiError(detail or f"HTTP {exc.code}") from exc
        except URLError as exc:
            raise ApiError(f"Backend indisponível: {exc.reason}") from exc
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ApiError(f"Resposta inválida do backend: {raw[:120]}") from exc
