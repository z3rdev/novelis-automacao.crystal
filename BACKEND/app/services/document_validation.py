"""Bounded content-validation cache keyed by fresh directory-entry metadata."""

import time
from collections import OrderedDict
from threading import RLock


class DocumentValidationCache:
    def __init__(self, max_entries=2048, max_age=30, clock=time.monotonic):
        self.max_entries, self.max_age, self.clock = max_entries, max_age, clock
        self._values = OrderedDict()
        self._lock = RLock()

    def read(self, path, fingerprint, kind, reader):
        if fingerprint is None:
            return reader(path)
        key = (path, kind)
        with self._lock:
            cached = self._values.get(key)
            if cached and cached[0] == fingerprint and self.clock() - cached[1] < self.max_age:
                self._values.move_to_end(key)
                return cached[2]
        value = reader(path)
        with self._lock:
            self._values[key] = (fingerprint, self.clock(), value)
            self._values.move_to_end(key)
            while len(self._values) > self.max_entries:
                self._values.popitem(last=False)
        return value


content_cache = DocumentValidationCache()
