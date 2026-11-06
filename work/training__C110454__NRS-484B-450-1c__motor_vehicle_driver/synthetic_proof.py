"""Import bridge for the runnable hyphenated proof script."""
import importlib.util
from pathlib import Path

_path = Path(__file__).with_name("synthetic-proof.py")
_spec = importlib.util.spec_from_file_location("parking_synthetic_proof", _path)
_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_module)
sample = _module.sample
