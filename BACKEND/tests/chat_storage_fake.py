"""In-memory S3 used only by controlled tests, with no external writes."""

from io import BytesIO
from types import SimpleNamespace
from unittest.mock import Mock

from botocore.exceptions import ClientError


class MemoryS3:
    def __init__(self):
        self.data, self.lifecycle = {}, []
        self.fail_copy = False
        self.meta = SimpleNamespace(events=SimpleNamespace(register_first=Mock()))

    def get_bucket_policy(self, **kwargs):
        return {"Policy": '{"Statement":[]}'}

    def put_object(self, *, Key, Body, Metadata, **kwargs):
        self.data[Key] = (bytes(Body), dict(Metadata))

    def head_object(self, *, Key, **kwargs):
        body, metadata = self.data[Key]
        return {"ContentLength": len(body), "Metadata": metadata}

    def get_object(self, *, Key, **kwargs):
        return {"Body": BytesIO(self.data[Key][0])}

    def copy_object(self, *, Key, CopySource, **kwargs):
        if self.fail_copy:
            raise RuntimeError("Controlled copy failure")
        self.data[Key] = self.data[CopySource["Key"]]

    def delete_object(self, *, Key, **kwargs):
        self.data.pop(Key, None)

    def get_paginator(self, _):
        return self

    def paginate(self, *, Prefix, **kwargs):
        return [{"Contents": [{"Key": key} for key in list(self.data) if key.startswith(Prefix)]}]

    def get_bucket_lifecycle_configuration(self, **kwargs):
        if not self.lifecycle:
            raise ClientError(
                {"Error": {"Code": "NoSuchLifecycleConfiguration"}},
                "GetBucketLifecycleConfiguration",
            )
        return {"Rules": self.lifecycle}

    def put_bucket_lifecycle_configuration(self, *, LifecycleConfiguration, **kwargs):
        self.lifecycle = LifecycleConfiguration["Rules"]
