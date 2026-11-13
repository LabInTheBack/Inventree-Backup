"""Real cross-process file-lock checks in a disposable temporary directory."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from support import PLUGIN_DIR, modules


class HardwareLockTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "hardware.lock"
        lock = patch.object(modules.locking, "lock_path", return_value=self.path)
        lock.start()
        self.addCleanup(lock.stop)

    def child_attempt(self):
        code = """
import importlib.util
import sys
from pathlib import Path
spec = importlib.util.spec_from_file_location('hardware_lock_test', sys.argv[1])
locking = importlib.util.module_from_spec(spec)
spec.loader.exec_module(locking)
locking.lock_path = lambda: Path(sys.argv[2])
try:
    with locking.hardware_action():
        print('acquired')
except locking.LocatorBusyError:
    print('busy')
"""
        return subprocess.run(
            [sys.executable, "-B", "-c", code, str(PLUGIN_DIR / "locking.py"), str(self.path)],
            capture_output=True, text=True, check=True, timeout=10,
        ).stdout.strip()

    def test_separate_process_is_rejected_until_the_action_finishes(self):
        with modules.locking.hardware_action():
            self.assertEqual(self.child_attempt(), "busy")
        self.assertEqual(self.child_attempt(), "acquired")
        self.assertTrue(self.path.exists())

    def test_nested_calls_keep_the_outer_lock_until_exit(self):
        with modules.locking.hardware_action():
            with modules.locking.hardware_action():
                pass
            self.assertEqual(self.child_attempt(), "busy")
        self.assertEqual(self.child_attempt(), "acquired")

    def test_exception_releases_the_lock(self):
        with self.assertRaises(RuntimeError):
            with modules.locking.hardware_action():
                raise RuntimeError("simulated controller failure")
        self.assertEqual(self.child_attempt(), "acquired")
