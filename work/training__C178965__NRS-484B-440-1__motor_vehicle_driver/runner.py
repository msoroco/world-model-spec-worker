"""Canonical first-case alias; exact bundled runners live under native/cases."""
import runpy
from pathlib import Path
runpy.run_path(str(Path(__file__).resolve().parent / "native/runner.py"), run_name="__main__")
