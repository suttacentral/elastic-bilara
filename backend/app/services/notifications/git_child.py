"""Linux query guardian, independent of the web worker's Python cleanup.

The worker alone owns the lease pipe's write end. EOF means cancellation or
worker death. Git has its own process group; this guardian survives killing that
group and reaps it before releasing the inherited query/execution locks.
"""
from contextlib import suppress
import ctypes
import os
import selectors
import signal
import subprocess
import sys


def main():
    lease = int(sys.argv[1])
    libc = ctypes.CDLL(None, use_errno=True)
    # PR_SET_CHILD_SUBREAPER: collect Git helpers as well as the direct child.
    if libc.prctl(36, 1, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Unable to supervise Git descendants")
    with selectors.DefaultSelector() as events:
        events.register(lease, selectors.EVENT_READ)
        if events.select(0):
            return 1  # Worker already died/cancelled before guardian startup.
        process = subprocess.Popen(sys.argv[2:], start_new_session=True)
        try:
            # pidfd reports exit without reaping the group leader. Its PID stays
            # reserved until killpg, so a reused PID cannot target another query.
            pidfd = os.pidfd_open(process.pid)
            try:
                events.register(pidfd, selectors.EVENT_READ)
                events.select()
            finally:
                os.close(pidfd)
        finally:
            with suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            while True:
                try:
                    os.waitpid(-1, 0)
                except ChildProcessError:
                    break
    return process.returncode if process.returncode >= 0 else 128 - process.returncode


if __name__ == "__main__":
    sys.exit(main())
