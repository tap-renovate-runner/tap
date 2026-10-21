"""One heavy pytest run per stack, and a way to stop it (tap#1092).

Two things sessions kept doing by hand, both unreliable:

* **Polling "is pytest running?"** fires in the gap between two plugin suites, so a second run
  started while the lane was between suites. A lock cannot have a gap: ``hold_pytest_lock`` takes an
  exclusive ``flock`` for the whole run and a second run waits (and says who holds it).
* **Stopping a lane.** ``docker exec`` does not forward a signal, so stopping the host-side script left
  ``tap.lane_run`` launching suite after suite, and killing its pytest left orphaned xdist workers.
  ``run_group`` starts pytest in its own process group and, on TERM or INT, kills the whole group;
  ``stop`` signals whoever holds the lock.

The lock file lives inside the container (``/tmp``), so its scope is one stack — the same scope as
the shared test database. A child started under a holder inherits ``TAP_PYTEST_LOCK_HELD`` and does not
try to take the lock again.

Usage inside the container::

    uv run python -m tap.pytest_lock run -- <pytest args>   # serial pytest: lock + process group
    uv run python -m tap.pytest_lock status                 # who holds it
    uv run python -m tap.pytest_lock stop                   # TERM the holder (it kills its group)
"""

from __future__ import annotations

import argparse
import fcntl
import os
import signal
import subprocess  # nosec B404 — fixed argv (this interpreter + `-m pytest` + caller's pytest args): the lane's own child, never a shell
import sys
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_HELD_ENV = "TAP_PYTEST_LOCK_HELD"
_PATH_ENV = "TAP_PYTEST_LOCK"
_DEFAULT_PATH = "/tmp/tap-pytest.lock"  # nosec B108 # noqa: S108 — container-local by design: one lock per stack


class LockBusy(RuntimeError):
    """Another run holds the lock (raised only for a non-waiting attempt)."""


def lock_path() -> Path:
    return Path(os.environ.get(_PATH_ENV, _DEFAULT_PATH))


def holder_text(path: Path | None = None) -> str:
    """What the current holder wrote into the lock file (``who pid=N since=...``), or ''."""
    try:
        return (path or lock_path()).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def is_locked(path: Path | None = None) -> bool:
    """True when some process holds the lock right now (the file text alone can be stale)."""
    target = path or lock_path()
    try:
        fd = os.open(target, os.O_RDWR)
    except OSError:
        return False
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(fd, fcntl.LOCK_UN)
        return False
    finally:
        os.close(fd)


def holder_pid(path: Path | None = None) -> int | None:
    for token in holder_text(path).split():
        if token.startswith("pid="):
            try:
                return int(token[4:])
            except ValueError:
                return None
    return None


@contextmanager
def hold_pytest_lock(who: str, *, wait: bool = True, path: Path | None = None) -> Iterator[None]:
    """Hold the stack's pytest lock for the duration; a no-op when an ancestor already holds it."""
    if os.environ.get(_HELD_ENV) == "1":
        yield
        return
    target = path or lock_path()
    fd = os.open(target, os.O_CREAT | os.O_RDWR, 0o666)
    try:
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if not wait:
                raise LockBusy(
                    f"another pytest run holds {target}: {holder_text(target) or 'unknown holder'}"
                ) from None
            sys.stderr.write(f"waiting for another pytest run in this stack to finish: {holder_text(target)}\n")
            sys.stderr.flush()
            fcntl.flock(fd, fcntl.LOCK_EX)
        os.ftruncate(fd, 0)
        os.write(fd, f"{who} pid={os.getpid()} since={time.strftime('%H:%M:%S')}\n".encode())
        os.environ[_HELD_ENV] = "1"
        try:
            yield
        finally:
            os.environ.pop(_HELD_ENV, None)
    finally:
        os.close(fd)  # closing releases the flock


_child: subprocess.Popen[str] | None = None


def _kill_group(sig: int = signal.SIGTERM, grace: float = 5.0) -> None:
    """Signal the child's whole process group, then SIGKILL stragglers after ``grace`` seconds."""
    proc = _child
    if proc is None or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, sig)
    except ProcessLookupError:
        return
    deadline = time.monotonic() + grace
    while time.monotonic() < deadline and proc.poll() is None:
        time.sleep(0.1)
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


def _on_stop(signum: int, _frame: object) -> None:
    _kill_group(signal.SIGTERM)
    raise SystemExit(128 + signum)


def run_group(argv: list[str], env: dict[str, str], *, capture: bool = False) -> tuple[int, str]:
    """Run ``argv`` in its own process group; TERM/INT to this process kills the whole group.

    ``capture=True`` returns the child's combined output (and still shows nothing until it ends);
    otherwise the child writes straight to this process's stdout/stderr and the text is ''.
    """
    global _child
    old = {s: signal.signal(s, _on_stop) for s in (signal.SIGTERM, signal.SIGINT)}
    try:
        # argv is a list built by the caller from this interpreter and validated pytest tokens
        # (tap.lane_run._checked_args); start_new_session=True makes the child its own group leader.
        _child = subprocess.Popen(  # nosec B603  # nosemgrep  # NOSONAR (S8705)
            argv,
            env=env,
            text=True,
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.STDOUT if capture else None,
            start_new_session=True,
            shell=False,
        )  # noqa: S603 — fixed argv head, validated tail
        out, _ = _child.communicate()
        return _child.returncode, out or ""
    finally:
        _child = None
        for s, handler in old.items():
            signal.signal(s, handler)


def stop(path: Path | None = None) -> str:
    """TERM the lock holder (which kills its pytest group). Returns a one-line report."""
    pid = holder_pid(path) if is_locked(path) else None
    if pid is None:
        return "no pytest run holds the lock"
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return f"holder pid {pid} is already gone (stale lock file); nothing to stop"
    return (
        f"sent TERM to {holder_text(path)}; it kills its pytest group. "
        "Stale test_tap* DBs may remain — use --create-db on the next run."
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tap.pytest_lock", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    run = sub.add_parser("run", help="run pytest under the stack lock, in its own process group")
    run.add_argument("pytest_args", nargs="*")
    sub.add_parser("status", help="print who holds the lock")
    sub.add_parser("stop", help="TERM the holder")
    args = parser.parse_args(argv)
    if args.cmd == "status":
        sys.stdout.write((holder_text() if is_locked() else "") or "no pytest run holds the lock")
        sys.stdout.write("\n")
        return 0
    if args.cmd == "stop":
        sys.stdout.write(stop() + "\n")
        return 0
    extra = [a for a in args.pytest_args if a != "--"]
    with hold_pytest_lock("tap.pytest_lock run"):
        rc, _ = run_group([sys.executable, "-m", "pytest", *extra], dict(os.environ))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
