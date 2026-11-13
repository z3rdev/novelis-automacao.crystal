"""Use the Windows certificate store without exporting the private key.

The selection rule is restricted to the CT-e portal and an exact subject/issuer.
The automation uses its own disposable browser profile; Windows policies stay intact.
"""

import base64
import json
import os
import re
import subprocess
from datetime import datetime

from app.automation.cancellation import check_cancelled
from app.automation.cancellable_process import run_process

PATTERN = "https://[*.]cte.fazenda.gov.br"


def windows_certificates() -> list[dict]:
    if os.name != "nt":
        raise RuntimeError("Selecao do certificado instalado requer Windows.")
    script = r"""
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$now = Get-Date
$store = [Security.Cryptography.X509Certificates.X509Store]::new('My', 'CurrentUser')
$store.Open([Security.Cryptography.X509Certificates.OpenFlags]::ReadOnly)
try {
$items = @($store.Certificates | Where-Object {
    $_.HasPrivateKey -and $_.NotBefore -le $now -and $_.NotAfter -gt $now
} | ForEach-Object {
    [pscustomobject]@{
        subject = $_.Subject
        subjectCN = $_.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $false)
        issuerCN = $_.GetNameInfo([Security.Cryptography.X509Certificates.X509NameType]::SimpleName, $true)
        thumbprint = $_.Thumbprint
        notAfter = $_.NotAfter.ToUniversalTime().ToString('o')
    }
})
ConvertTo-Json -InputObject $items -Compress
} finally { $store.Close() }
"""
    try:
        result = run_process(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-EncodedCommand",
             base64.b64encode(script.encode("utf-16-le")).decode("ascii")],
            capture_output=True, timeout=20, creationflags=subprocess.CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("Consulta aos certificados do Windows excedeu 20 segundos.") from exc
    if result.returncode:
        raise RuntimeError("Nao foi possivel consultar os certificados do usuario do Windows.")
    return json.loads(result.stdout.decode("utf-8-sig").strip() or "[]")


def select_certificate(certificates: list[dict], cnpj: str, thumbprint: str = "") -> dict:
    digits = re.sub(r"\D", "", cnpj)
    thumb = thumbprint.replace(" ", "").upper()
    if not thumb and len(digits) != 14:
        raise ValueError("Informe o CNPJ de 14 digitos do certificado SEFAZ.")
    candidates = [cert for cert in certificates
                  if (not thumb or cert["thumbprint"].upper() == thumb)
                  and (not digits or digits in cert["subjectCN"])]
    if not candidates:
        raise RuntimeError("Certificado SEFAZ configurado nao foi encontrado valido e com chave privada neste usuario do Windows.")
    if len(candidates) > 1:
        raise RuntimeError("Ha mais de um certificado valido para este CNPJ; configure XML_SEFAZ_CERTIFICATE_THUMBPRINT.")
    cert = candidates[0]
    if datetime.fromisoformat(cert["notAfter"].replace("Z", "+00:00")).timestamp() <= datetime.now().timestamp():
        raise RuntimeError("Certificado SEFAZ expirado.")
    return cert


def certificate_rule(cert: dict) -> dict:
    return {"pattern": PATTERN, "filter": {
        "SUBJECT": {"CN": cert["subjectCN"]}, "ISSUER": {"CN": cert["issuerCN"]},
    }}


def configure_certificate(config: dict) -> dict | None:
    cnpj = str(config.get("certificateCnpj") or "")
    thumb = str(config.get("certificateThumbprint") or "")
    if not cnpj and not thumb:
        return None
    cert = select_certificate(windows_certificates(), cnpj, thumb)
    check_cancelled()
    return cert
