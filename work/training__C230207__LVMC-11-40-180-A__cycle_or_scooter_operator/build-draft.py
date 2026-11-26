"""Compatibility entrypoint for rebuilding both controlled Native drafts."""
from pathlib import Path
import runpy

runpy.run_path(str(Path(__file__).with_name('build-controlled-drafts.py')), run_name='__main__')
