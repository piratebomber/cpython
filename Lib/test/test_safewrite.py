import os
import stat
import tempfile
import unittest

from safewrite import safewrite


class TestSafeWrite(unittest.TestCase):
    def test_happy_path_text(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "t.txt")
            with safewrite(path, "w", encoding="utf-8") as f:
                f.write("hello world")

            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            self.assertEqual(data, "hello world")

    def test_exception_rolls_back_no_target(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "noexist.txt")
            with self.assertRaises(RuntimeError):
                with safewrite(path, "w", encoding="utf-8") as f:
                    f.write("partial")
                    raise RuntimeError("boom")

            # Target must not exist after a failed write
            self.assertFalse(os.path.exists(path))

    def test_exception_preserves_existing_target(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "exists.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("original")

            with self.assertRaises(RuntimeError):
                with safewrite(path, "w", encoding="utf-8") as f:
                    f.write("partial")
                    raise RuntimeError("boom")

            # original content must still be there
            with open(path, "r", encoding="utf-8") as f:
                data = f.read()
            self.assertEqual(data, "original")

    def test_preserve_mode_posix(self):
        # Permission preservation is a POSIX concept; skip on Windows
        if os.name == "nt":
            self.skipTest("posix permissions not supported on Windows")

        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "perm.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("x")
            os.chmod(path, 0o640)

            with safewrite(path, "w", encoding="utf-8") as f:
                f.write("new")

            st = os.stat(path)
            # Keep the file mode bits that were set (owner/group/other)
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o640)


if __name__ == "__main__":
    unittest.main()
