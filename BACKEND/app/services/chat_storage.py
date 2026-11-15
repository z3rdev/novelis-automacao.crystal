"""Private GNRE objects and a dedicated S3 lifecycle for confirmed tickets."""

from base64 import b64encode
from hashlib import md5, sha256
from uuid import UUID

from app.domain.chat import ChatStorageError, cte_code
from app.services.chat_files import MAX_UPLOAD
from app.services.execution_reports.storage import ReportStorage
from app.services.minio_config import operational_client
from app.services.releases.config import BUCKET

PREFIX = "cargo-hub/gnre/"
PENDING = PREFIX + "pending/"
ARCHIVE = PREFIX + "archive/"
LIFECYCLE_ID = "cargo-hub-gnre-archive-30-days"


def lifecycle_checksum(params, **kwargs):
    params["headers"]["Content-MD5"] = b64encode(
        md5(params["body"], usedforsecurity=False).digest()
    ).decode("ascii")


class ChatObjectStorage:
    def __init__(self, backend_root, config, client=None):
        self.root, self.config, self._client = backend_root, config, client

    def client(self):
        if self._client is None:
            self._client = operational_client(self.root, self.config, "GNRE_S3_CREDENTIALS_FILE")
        if self._client is None:
            raise ChatStorageError(
                "O armazenamento de GNRE no MinIO não está configurado neste computador."
            )
        return self._client

    @staticmethod
    def key(cte, metadata):
        kind = metadata["kind"]
        if kind not in {"guia", "comprovante", "combined"}:
            raise ChatStorageError("Tipo de documento inválido.")
        return f"{PENDING}{cte_code(cte)}/{UUID(metadata['id'])}/{kind}.pdf"

    @staticmethod
    def valid_key(cte, key):
        if (
            not key.startswith((f"{PENDING}{cte_code(cte)}/", f"{ARCHIVE}{cte_code(cte)}/"))
            or ".." in key
        ):
            raise ChatStorageError("Endereço do documento inválido.")

    def write(self, cte, metadata, data):
        key = self.key(cte, metadata)
        try:
            client = self.client()
            ReportStorage.ensure_private(client, key)
            client.put_object(
                Bucket=BUCKET,
                Key=key,
                Body=data,
                ContentType="application/pdf",
                CacheControl="private, no-store",
                Metadata={"sha256": metadata["sha256"]},
            )
            self.verify(client, key, metadata["sha256"], len(data))
        except ChatStorageError:
            raise
        except Exception:  # noqa: BLE001 - never expose SDK requests or private storage configuration
            raise ChatStorageError(
                "Não foi possível confirmar o envio do documento ao MinIO."
            ) from None
        metadata["object_key"] = key

    @staticmethod
    def verify(client, key, digest, size=None):
        head = client.head_object(Bucket=BUCKET, Key=key)
        metadata = {key.lower(): value for key, value in head.get("Metadata", {}).items()}
        if metadata.get("sha256") != digest or (
            size is not None and head.get("ContentLength") != size
        ):
            raise ChatStorageError("A integridade do documento no MinIO não foi confirmada.")

    def read(self, cte, metadata):
        key = metadata["object_key"]
        self.valid_key(cte, key)
        try:
            response = self.client().get_object(Bucket=BUCKET, Key=key)
            with response["Body"] as body:
                data = body.read(MAX_UPLOAD * 2 + 1)
            if len(data) > MAX_UPLOAD * 2 or sha256(data).hexdigest() != metadata["sha256"]:
                raise ChatStorageError(
                    "A integridade do documento baixado do MinIO não foi confirmada."
                )
            return data
        except ChatStorageError:
            raise
        except Exception:  # noqa: BLE001 - sanitize errors from the storage provider
            raise ChatStorageError("O documento está indisponível no MinIO.") from None

    def objects(self, prefix):
        for page in (
            self.client().get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=prefix)
        ):
            for value in page.get("Contents", []):
                yield value["Key"]

    def archive(self, row):
        client = self.client()
        source = f"{PENDING}{cte_code(row['cte'])}/"
        target = f"{ARCHIVE}{cte_code(row['cte'])}/{UUID(str(row['archive_id']))}/"
        ReportStorage.ensure_private(client, target + "probe.pdf")
        for key in self.objects(source):
            self.valid_key(row["cte"], key)
            head = client.head_object(Bucket=BUCKET, Key=key)
            metadata = {name.lower(): value for name, value in head.get("Metadata", {}).items()}
            new_key = target + key.removeprefix(source)
            client.copy_object(
                Bucket=BUCKET,
                Key=new_key,
                CopySource={"Bucket": BUCKET, "Key": key},
                MetadataDirective="COPY",
            )
            self.verify(client, new_key, metadata.get("sha256"), head["ContentLength"])
        updated = {}
        for kind in ("guia", "comprovante", "combined"):
            metadata = row.get(kind)
            if metadata:
                key = metadata["object_key"]
                new_key = target + key.removeprefix(source) if key.startswith(source) else key
                self.valid_key(row["cte"], new_key)
                self.verify(client, new_key, metadata["sha256"])
                updated[kind] = {
                    **metadata,
                    "object_key": new_key,
                    "expires_at": row["expires_at"].isoformat(),
                }
        return updated

    def remove_pending(self, cte):
        for key in self.objects(f"{PENDING}{cte_code(cte)}/"):
            self.valid_key(cte, key)
            self.client().delete_object(Bucket=BUCKET, Key=key)

    def ensure_retention(self):
        from botocore.exceptions import ClientError

        client = self.client()
        try:
            rules = client.get_bucket_lifecycle_configuration(Bucket=BUCKET).get("Rules", [])
        except ClientError as error:
            if error.response.get("Error", {}).get("Code") != "NoSuchLifecycleConfiguration":
                raise
            rules = []
        rule = {
            "ID": LIFECYCLE_ID,
            "Status": "Enabled",
            "Filter": {"Prefix": ARCHIVE},
            "Expiration": {"Days": 30},
        }
        if rule not in rules:
            rules = [value for value in rules if value.get("ID") != LIFECYCLE_ID] + [rule]
            client.meta.events.register_first(
                "before-call.s3.PutBucketLifecycleConfiguration",
                lifecycle_checksum,
                unique_id=LIFECYCLE_ID,
            )
            client.put_bucket_lifecycle_configuration(
                Bucket=BUCKET, LifecycleConfiguration={"Rules": rules}
            )
        return rule
