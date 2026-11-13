import subprocess
import time

from app.automation.cancellation import cancel_on_stop, check_cancelled, current_cancellation


def run_process(command, **kwargs):
    if current_cancellation() is None:
        return subprocess.run(command, check=kwargs.pop("check", False), **kwargs)
    timeout = kwargs.pop("timeout", None)
    data = kwargs.pop("input", None)
    kwargs.pop("capture_output", None)
    kwargs.pop("check", None)
    check_cancelled()
    started = time.monotonic()
    with subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, **kwargs) as process:
        try:
            with cancel_on_stop(process.kill):
                while True:
                    check_cancelled()
                    try:
                        output, error = process.communicate(input=data, timeout=0.1)
                        check_cancelled()
                        return subprocess.CompletedProcess(command, process.returncode, output, error)
                    except subprocess.TimeoutExpired:
                        data = None
                        if timeout is not None and time.monotonic() - started >= timeout:
                            process.kill()
                            output, error = process.communicate()
                            raise subprocess.TimeoutExpired(command, timeout, output, error) from None
        finally:
            if process.poll() is None:
                process.kill()
            process.communicate()
