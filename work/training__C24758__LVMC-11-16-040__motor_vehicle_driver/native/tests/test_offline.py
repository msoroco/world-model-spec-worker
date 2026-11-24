import subprocess
import sys
import unittest
import ast
from pathlib import Path


class ExactPrimaryOffline(unittest.TestCase):
    def test_case_and_capture_contract(self):
        subprocess.run([sys.executable, "runner.py", "--check"], check=True)

    def test_source_bound_sight_speed(self):
        subprocess.run([sys.executable, "prove_sight_speed_measure.py"], check=True)

    def test_four_camera_saved_source(self):
        subprocess.run([sys.executable, "prove_saved_source.py"], check=True)

    def test_native_capture_source_is_cpu_parseable(self):
        source = Path("native_capture.py").read_text()
        ast.parse(source)
        assert "for i in range(600)" in source
        assert "world.tick()" in source
        assert "native-ego-readback.jsonl" in source


if __name__ == "__main__":
    unittest.main()
