"""Owned notification Git queries for synchronous and asynchronous callers."""
import asyncio
from contextlib import contextmanager, suppress
import os
from pathlib import Path
import subprocess
import sys


@contextmanager
def guarded_command(command, lock_fds=()):
    reader, writer = os.pipe()
    try:
        launcher = Path(__file__).with_name('git_child.py')
        yield [sys.executable, str(launcher), str(reader), *command], (reader, *lock_fds)
    finally:
        # Only the guardian gets reader/locks. No subprocess inherits writer.
        # Closing it is the same signal on normal cancellation and SIGKILL.
        os.close(writer)
        os.close(reader)


async def run_async(command, *, cwd, lock_fds=()):
    process = None
    try:
        with guarded_command(command, lock_fds) as (args, fds):
            launch = asyncio.create_task(asyncio.create_subprocess_exec(
                *args, cwd=cwd, stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE, pass_fds=fds, start_new_session=True,
            ))
            try:
                process = await asyncio.shield(launch)
                stdout, stderr = await process.communicate()
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            finally:
                # Cancellation during spawn must still recover the guardian handle.
                if process is None:
                    with suppress(OSError):
                        process = await launch
    finally:
        if process is not None:
            # Lease is closed first. Drain output while the guardian kills/reaps
            # the query; don't SIGKILL the guardian and lose its cleanup.
            await process.communicate()


def run(command, *, cwd, text=False, timeout=None):
    process = None
    try:
        with guarded_command(command) as (args, fds):
            process = subprocess.Popen(
                args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=text, pass_fds=fds, start_new_session=True,
            )
            stdout, stderr = process.communicate(timeout=timeout)
            return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
    finally:
        if process is not None:
            process.communicate()
