"""Invoke the exact pinned selected-manifest validator without changing runtime."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path[:0] = [str(ROOT/'runtime/pipeline'),
                str(ROOT/'runtime/pipeline/scenario_pipeline')]
from scenario_pipeline.worker_exchange.execution_manifest import validate

validate(ROOT, HERE.name)
