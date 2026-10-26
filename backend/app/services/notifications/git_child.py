"""Linux exec wrapper: Git must not survive an abruptly killed web worker."""
import ctypes
import os
import signal
import sys


def main():
    parent = int(sys.argv[1])
    libc = ctypes.CDLL(None, use_errno=True)
    # PR_SET_PDEATHSIG; run here rather than a preexec_fn in a threaded worker.
    if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:
        raise OSError(ctypes.get_errno(), "Unable to set parent-death signal")
    if os.getppid() != parent:
        sys.exit(1)
    os.execvp(sys.argv[2], sys.argv[2:])


if __name__ == "__main__":
    main()
