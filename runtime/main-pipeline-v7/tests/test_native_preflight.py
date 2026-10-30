import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from worker_exchange.runtime_cli import capture,native_preflight


class NativePreflightTests(unittest.TestCase):
    def test_missing_carla_fails_before_attempt_directory(self):
        class Failure:
            returncode=1
            stderr='ModuleNotFoundError: No module named carla'
            stdout=''
        with tempfile.TemporaryDirectory() as tmp,patch('worker_exchange.runtime_cli.subprocess.run',return_value=Failure()):
            attempt=Path(tmp)/'attempt'
            with self.assertRaisesRegex(ValueError,'Native Python import preflight failed'):
                capture('unused-manifest','case',attempt,'127.0.0.1',22100,'/native/python')
            self.assertFalse(attempt.exists())


if __name__=='__main__':unittest.main()
