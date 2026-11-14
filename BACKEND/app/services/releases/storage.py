import asyncio
import json
import re

from pydantic import ValidationError

from app.services.releases.config import BUCKET, PREFIX, DeveloperConfig
from app.services.releases.manifest import ReleaseManifest, version_parts


def storage_error(error: Exception) -> ValueError:
    code = getattr(error, "response", {}).get("Error", {}).get("Code", "")
    if code in {"PreconditionFailed", "ConditionalRequestConflict", "412", "409"}:
        return ValueError("Outra publicação alterou a release. Verifique a versão disponível e tente novamente.")
    if code in {"AccessDenied", "InvalidAccessKeyId", "SignatureDoesNotMatch"}:
        return ValueError("As credenciais locais não autorizaram esta operação no servidor de releases.")
    return ValueError("A operação autenticada no servidor de releases falhou. Verifique a conexão e as permissões.")


class ReleaseStorage:
    def __init__(self, config: DeveloperConfig, prefix: str = PREFIX):
        self.config = config
        self.prefix = prefix

    def enabled(self) -> bool:
        return self.config.enabled()

    def read_manifest(self, client=None) -> tuple[ReleaseManifest | None, str | None]:
        from botocore.exceptions import BotoCoreError, ClientError

        client = client or self.config.client()
        try:
            response = client.get_object(Bucket=BUCKET, Key=self.prefix + "latest.json")
            with response["Body"] as stream:
                content = stream.read(65537)
            if len(content) > 65536:
                raise ValueError("O manifesto de atualização excede o tamanho permitido.")
            return ReleaseManifest.model_validate_json(content), response["ETag"]
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"NoSuchKey", "NoSuchObject", "404"}:
                return None, None
            raise storage_error(exc) from None
        except BotoCoreError as exc:
            raise storage_error(exc) from None

    async def chunks(self, release: ReleaseManifest):
        from botocore.exceptions import BotoCoreError, ClientError

        client = await asyncio.to_thread(self.config.client)
        body = None
        try:
            response = await asyncio.to_thread(client.get_object, Bucket=BUCKET, Key=self.prefix + release.package_key())
            body = response["Body"]
            while chunk := await asyncio.to_thread(body.read, 65536):
                yield chunk
        except (BotoCoreError, ClientError) as exc:
            raise storage_error(exc) from None
        finally:
            if body is not None:
                body.close()

    def probe(self) -> dict:
        if not self.enabled():
            raise PermissionError("Modo desenvolvedor desativado.")
        try:
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError:
            return {"authenticated": False, "message": "Instale a dependência de desenvolvimento boto3."}
        try:
            client = self.config.client()
            values = client.list_objects_v2(Bucket=BUCKET, Prefix=self.prefix, MaxKeys=20)
            release, _ = self.read_manifest(client)
            return {"authenticated": True, "objects_found": len(values.get("Contents", [])),
                    "manifest_present": release is not None,
                    "message": "Acesso autenticado ao prefixo de releases confirmado."}
        except ValidationError:
            return {"authenticated": False, "message": "O manifesto do servidor possui formato inválido."}
        except ValueError as exc:
            return {"authenticated": False, "message": str(exc)}
        except (OSError, BotoCoreError, ClientError) as exc:
            return {"authenticated": False, "message": str(storage_error(exc))}

    def catalog_latest(self, client) -> ReleaseManifest:
        keys = []
        token = {}
        while True:
            page = client.list_objects_v2(Bucket=BUCKET, Prefix=self.prefix + "releases/", **token)
            for item in page.get("Contents", []):
                relative = item["Key"].removeprefix(self.prefix)
                match = re.fullmatch(r"releases/(\d+\.\d+\.\d+(?:-r[1-9]\d*)?)/([a-f0-9]{64})\.json", relative)
                if match:
                    keys.append((version_parts(match[1]), item["Key"], match[1], match[2]))
            if not page.get("IsTruncated"):
                break
            token = {"ContinuationToken": page["NextContinuationToken"]}
        if not keys:
            raise ValueError("O catálogo de releases está indisponível.")
        highest = max(entry[0] for entry in keys)
        winners = [entry for entry in keys if entry[0] == highest]
        if len(winners) != 1:
            raise ValueError("Há pacotes diferentes para a mesma versão. Publique uma nova versão para resolver o conflito.")
        _, key, version, sha256 = winners[0]
        response = client.get_object(Bucket=BUCKET, Key=key)
        with response["Body"] as stream:
            content = stream.read(65537)
        if len(content) > 65536:
            raise ValueError("O registro de release excede o tamanho permitido.")
        release = ReleaseManifest.model_validate_json(content)
        if release.version != version or release.sha256.lower() != sha256:
            raise ValueError("O registro de release difere de sua identificação no catálogo.")
        return release

    def commit_manifest(self, client, release: ReleaseManifest) -> ReleaseManifest:
        from botocore.exceptions import BotoCoreError, ClientError

        if not self.enabled():
            raise PermissionError("Modo desenvolvedor desativado durante a publicação.")
        try:
            record = json.dumps(release.model_dump(mode="json"), ensure_ascii=False).encode("utf-8")
            client.put_object(Bucket=BUCKET,
                Key=self.prefix + f"releases/{release.version}/{release.sha256.lower()}.json",
                Body=record, ContentType="application/json")
            # Older MinIO deployments can ignore conditional PUT headers. Reconcile
            # the version catalog before and after updating the compatibility pointer.
            for _ in range(3):
                if not self.enabled():
                    raise PermissionError("Modo desenvolvedor desativado durante a publicação.")
                selected = self.catalog_latest(client)
                current, current_etag = self.read_manifest(client)
                if current and version_parts(current.version) > version_parts(selected.version):
                    return current
                if current is None or current.version != selected.version or current.sha256 != selected.sha256:
                    condition = {"IfMatch": current_etag} if current_etag else {"IfNoneMatch": "*"}
                    try:
                        client.put_object(Bucket=BUCKET, Key=self.prefix + "latest.json",
                            Body=json.dumps(selected.model_dump(mode="json"), ensure_ascii=False).encode("utf-8"),
                            ContentType="application/json", CacheControl="no-cache", **condition)
                    except ClientError as exc:
                        if exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "ConditionalRequestConflict", "412", "409"}:
                            continue
                        raise
                latest = self.catalog_latest(client)
                confirmed, _ = self.read_manifest(client)
                if confirmed and latest.version == confirmed.version and latest.sha256 == confirmed.sha256:
                    return confirmed
            raise ValueError("O catálogo recebeu publicações simultâneas. Consulte a atualização e tente novamente.")
        except (BotoCoreError, ClientError) as exc:
            raise storage_error(exc) from None
