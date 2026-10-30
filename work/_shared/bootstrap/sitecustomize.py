"""Select the source-verified v3 worker runtime for frozen root launchers.

Set PYTHONPATH to this directory when invoking the root worker_check.py.
"""
import importlib.util
import sys
import types
from pathlib import Path

repo = Path(__file__).resolve().parents[3]
source = repo / 'work/_shared/runtime-v3.py'
spec = importlib.util.spec_from_file_location('_worker_verified_v3', source)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
runtime = module.runtime()
sys.path.insert(0, str(runtime / 'scenario_pipeline'))
sys.path.insert(1, str(runtime / 'python'))
resolver = types.ModuleType('overlay')
resolver.effective_runtime = lambda: runtime
sys.modules['overlay'] = resolver
