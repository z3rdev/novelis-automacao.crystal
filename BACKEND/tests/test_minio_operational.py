from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services.chat_storage import ChatObjectStorage
from app.services.execution_reports.storage import ReportStorage
from app.services.releases.config import DeveloperConfig


@pytest.mark.parametrize("filename", ["credentials.json", "minio.credentials.json"])
def test_operational_storage_works_without_developer_mode(tmp_path, monkeypatch, filename):
    (tmp_path / filename).write_text("{}")
    config = SimpleNamespace(get=lambda key: "")
    client = object()
    factory = Mock(return_value=client)
    monkeypatch.setattr("app.services.minio_config.s3_client", factory)
    assert ReportStorage(tmp_path, config).client() is client
    assert ChatObjectStorage(tmp_path, config).client() is client
    assert not DeveloperConfig(tmp_path).enabled()
    with pytest.raises(PermissionError):
        DeveloperConfig(tmp_path).client()
    assert all(call.args[0] == tmp_path / filename for call in factory.call_args_list)


def test_operational_purpose_credentials_take_precedence(tmp_path, monkeypatch):
    values = {"MINIO_CREDENTIALS_FILE": "common.json", "GNRE_S3_CREDENTIALS_FILE": "gnre.json"}
    config = SimpleNamespace(get=lambda key: values.get(key, ""))
    factory = Mock(return_value=object())
    monkeypatch.setattr("app.services.minio_config.s3_client", factory)
    ReportStorage(tmp_path, config).client()
    assert factory.call_args.args[0] == tmp_path / "common.json"
    ChatObjectStorage(tmp_path, config).client()
    assert factory.call_args.args[0] == tmp_path / "gnre.json"
