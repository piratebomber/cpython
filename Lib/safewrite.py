import os, tempfile, shutil, contextlib

@contextlib.contextmanager
def safewrite(path, mode="w", encoding="utf-8"):
    # Write atomically to a file, rolling back on error
    dir_ = os.path.dirname(path) or "."
    if "b" in mode:
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=dir_, mode=mode)
    else:
        tmp = tempfile.NamedTemporaryFile(delete=False, dir=dir_, mode=mode, encoding=encoding)
    try:
        yield tmp
        tmp.flush()
        os.fsync(tmp.fileno())
        tmp.close()
        shutil.move(tmp.name, path)
    except Exception:
        try:
            os.unlink(tmp.name)
        except FileNotFoundError:
            pass
        raise
