"""Safer atomic file writes.

This module provides a context manager `safewrite()` which writes data to a
temporary file in the same directory as the target and atomically replaces the
target on successful exit. It attempts to fsync the file and the containing
directory (on platforms that support it) so that the write is durable.

The implementation prefers os.replace() over shutil.move() to ensure the
operation is atomic on the same filesystem and doesn't accidentally copy the
file between filesystems.
"""

import os
import tempfile
import contextlib
from typing import IO, Iterator, Optional


@contextlib.contextmanager
def safewrite(path: str,
              mode: str = "w",
              encoding: Optional[str] = "utf-8",
              fsync: bool = True,
              preserve_mode: bool = True) -> Iterator[IO]:
    """Open a temporary file and atomically replace ``path`` on success.

    Parameters
    - path: destination path to write
    - mode: file mode string, e.g. 'w' or 'wb'
    - encoding: text encoding (used when writing text mode)
    - fsync: if True, call os.fsync() on the file and attempt to fsync the
      containing directory to increase durability
    - preserve_mode: if True and the destination exists, copy its file mode to
      the temporary file so permissions are preserved after replacement

    Yields the opened file object. If an exception is raised inside the
    context, the temporary file is removed and the original file is left
    untouched.
    """

    dirpath = os.path.dirname(path) or "."
    basename = os.path.basename(path)

    # Use mkstemp to get an fd we can control and set permissions on.
    flags = os.O_RDWR | os.O_CREAT | os.O_EXCL
    # create in same directory so os.replace() can be atomic
    fd, tmpname = tempfile.mkstemp(prefix=f".{basename}.", dir=dirpath)
    mode_is_binary = "b" in mode
    file_obj: IO
    try:
        # Optionally preserve mode
        if preserve_mode and os.path.exists(path):
            try:
                st = os.stat(path)
                try:
                    os.fchmod(fd, st.st_mode)
                except (AttributeError, PermissionError, OSError):
                    # fchmod may not be available on all platforms or may
                    # fail due to permissions; ignore and continue
                    pass
            except OSError:
                # If stat fails for any reason, continue without preserving
                pass

        # Wrap fd into a Python file object according to requested mode
        if mode_is_binary:
            file_obj = os.fdopen(fd, mode)
        else:
            # Text mode: fdopen handles encoding via the 'encoding' kw only
            # in Python 3.7+, so pass encoding if available.
            if encoding is not None:
                file_obj = os.fdopen(fd, mode, encoding=encoding)
            else:
                file_obj = os.fdopen(fd, mode)

        try:
            yield file_obj

            # Flush and optionally fsync the file
            file_obj.flush()
            if fsync:
                try:
                    os.fsync(file_obj.fileno())
                except OSError:
                    # If fsync is not supported, ignore
                    pass
            file_obj.close()

            # Atomically replace the target. Use os.replace which is atomic on
            # the same filesystem and overwrites the destination.
            try:
                os.replace(tmpname, path)
            except Exception:
                # If replace fails, try to remove tmp and raise
                try:
                    os.unlink(tmpname)
                except FileNotFoundError:
                    pass
                raise

            # Try to fsync the directory so that the rename is durable on POSIX.
            if fsync:
                try:
                    dirfd = os.open(dirpath or ".", os.O_RDONLY)
                    try:
                        os.fsync(dirfd)
                    finally:
                        os.close(dirfd)
                except (AttributeError, OSError):
                    # Not supported on this platform or failed; ignore
                    pass

        except Exception:
            # Ensure tmp file is removed on error inside the context
            try:
                file_obj.close()
            except Exception:
                pass
            try:
                os.unlink(tmpname)
            except FileNotFoundError:
                pass
            raise

    except Exception:
        # If we failed before wrapping fd into file object, make sure tmp is
        # removed to avoid stale temp files.
        try:
            if 'tmpname' in locals() and os.path.exists(tmpname):
                os.unlink(tmpname)
        except Exception:
            pass
        raise
