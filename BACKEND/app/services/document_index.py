"""Request-scoped directory listings, avoiding repeated negative SMB lookups."""

import os
from pathlib import Path
from threading import Lock, RLock

from app.automation.cancellation import check_cancelled
from app.services.cte_xml_files import read_xml_identity, validate_xml_identity
from app.services.document_validation import content_cache


class DocumentIndex:
    def __init__(self, validation_cache=None):
        self._directories = {}
        self._fingerprints = {}
        self._validation_cache = validation_cache or content_cache
        self._lock = RLock()
        self._directory_locks = {}

    def _listing(self, directory):
        directory = Path(directory)
        with self._lock:
            check_cancelled()
            if directory in self._directories:
                return self._directories[directory]
            parent = self._directories.get(directory.parent)
            if parent is not None and directory.name.casefold() not in parent[1]:
                self._directories[directory] = ([], set())
                return self._directories[directory]
            directory_lock = self._directory_locks.setdefault(directory, Lock())
        # Each directory has its own lock. An SMB scan for one CT-e must not
        # serialize all other document workers behind the shared cache lock.
        with directory_lock:
            with self._lock:
                if directory in self._directories:
                    return self._directories[directory]
            files, folders = [], set()
            try:
                with os.scandir(directory) as entries:
                    for entry in entries:
                        check_cancelled()
                        if entry.is_file():
                            path = Path(entry.path)
                            files.append(path)
                            if path.suffix.lower() in {".pdf", ".xml"}:
                                try:
                                    stat = entry.stat()
                                    self._fingerprints[path] = (
                                        stat.st_size,
                                        stat.st_mtime_ns,
                                        stat.st_ctime_ns,
                                    )
                                except OSError:
                                    pass
                        elif entry.is_dir():
                            folders.add(entry.name.casefold())
            except FileNotFoundError:
                pass
            with self._lock:
                self._directories[directory] = (files, folders)
            return files, folders

    def files(self, directory, extensions):
        files, _ = self._listing(directory)
        return [path for path in files if path.suffix.lower() in extensions]

    def validate_xml(self, path, row):
        check_cancelled()
        identity = self._validation_cache.read(
            path, self._fingerprints.get(path), "xml", read_xml_identity
        )
        validate_xml_identity(identity, row)

    def valid_pdf(self, path):
        check_cancelled()

        def read_header(file_path):
            with file_path.open("rb") as file:
                header = file.read(6)
                return len(header) > 5 and header.startswith(b"%PDF-")

        return self._validation_cache.read(path, self._fingerprints.get(path), "pdf", read_header)
