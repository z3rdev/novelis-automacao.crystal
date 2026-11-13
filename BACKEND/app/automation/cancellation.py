"""Per-run cancellation shared with blocking workers and their owned resources."""

import asyncio
import logging
from contextlib import contextmanager
from contextvars import ContextVar
from threading import Event, Lock


class RunCancelled(asyncio.CancelledError):
    pass


_current = ContextVar("automation_cancellation", default=None)
logger = logging.getLogger(__name__)


class _Callback:
    def __init__(self, callback):
        self.callback = callback
        self.lock = Lock()
        self.active = True

    def invoke(self):
        with self.lock:
            if self.active:
                try:
                    self.callback()
                except (Exception, asyncio.CancelledError):
                    # The owning worker still has to finish/close before drain returns.
                    logger.debug("Recurso ja encerrado durante o cancelamento.", exc_info=True)

    def close(self):
        with self.lock:
            self.active = False


class RunCancellation:
    def __init__(self):
        self.cancelled = Event()
        self.loop = asyncio.get_running_loop()
        self.workers = set()
        self.callbacks = set()
        self.lock = Lock()

    def track(self, task):
        self.workers.add(task)

        def finished(value):
            self.workers.discard(value)
            if not value.cancelled():
                value.exception()

        task.add_done_callback(finished)

    def _launch(self, callback):
        self.track(asyncio.create_task(asyncio.to_thread(callback.invoke)))

    def request_cancel(self):
        if self.cancelled.is_set():
            return
        self.cancelled.set()
        with self.lock:
            for callback in self.callbacks:
                self.loop.call_soon_threadsafe(self._launch, callback)

    async def drain(self):
        while self.workers:
            await asyncio.gather(*list(self.workers), return_exceptions=True)


@contextmanager
def cancellation_scope(cancellation):
    token = _current.set(cancellation)
    try:
        yield
    finally:
        _current.reset(token)


def check_cancelled():
    cancellation = _current.get()
    if cancellation and cancellation.cancelled.is_set():
        raise RunCancelled("Execucao cancelada pelo usuario.")


@contextmanager
def cancel_on_stop(callback):
    cancellation = _current.get()
    hook = _Callback(callback)
    if cancellation:
        with cancellation.lock:
            cancellation.callbacks.add(hook)
            if cancellation.cancelled.is_set():
                cancellation.loop.call_soon_threadsafe(cancellation._launch, hook)
    try:
        check_cancelled()
        yield
        check_cancelled()
    finally:
        if cancellation:
            with cancellation.lock:
                cancellation.callbacks.discard(hook)
        hook.close()


async def run_blocking(function, *args, **kwargs):
    check_cancelled()
    cancellation = _current.get()
    if cancellation is None:
        return await asyncio.to_thread(function, *args, **kwargs)

    def execute():
        check_cancelled()
        value = function(*args, **kwargs)
        check_cancelled()
        return value

    worker = asyncio.create_task(asyncio.to_thread(execute))
    if cancellation:
        cancellation.track(worker)
    return await asyncio.shield(worker)


def current_cancellation():
    return _current.get()


@contextmanager
def cancellable_cursor(cursor):
    cancellation = _current.get()
    if cancellation is None:
        yield cursor
    else:
        with cancel_on_stop(cursor.cancel):
            yield cursor
