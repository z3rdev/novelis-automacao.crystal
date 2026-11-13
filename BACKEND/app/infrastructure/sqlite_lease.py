"""Bounded, cross-process file lock held only during one SQLite operation."""

import errno
import os
import time
from pathlib import Path


class WriterLease:
    def __init__(self, database: Path):
        self.path = database.with_suffix(database.suffix + ".writer.lock")
        self.stream = None

    def acquire(self, timeout: float = 30) -> None:
        if self.stream:
            return
        stream = self.path.open("a+b")
        try:
            if stream.tell() == 0:
                stream.write(b"\0")
                stream.flush()
            stream.seek(0)
            deadline = time.monotonic() + timeout
            while True:
                try:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    self.stream = stream
                    return
                except OSError as exc:
                    if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                        raise
                    if time.monotonic() >= deadline:
                        raise RuntimeError("SQLite ocupado por outra operacao. Tente novamente.") from None
                    time.sleep(0.05)
        finally:
            if self.stream is not stream:
                stream.close()

    def close(self) -> None:
        if self.stream:
            self.stream.close()
            self.stream = None
