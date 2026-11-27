"""Dispatch one exact C405647 Native case using the tested package runner."""

import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
runpy.run_path(str(HERE / "native" / "runner.py"), run_name="__main__")
