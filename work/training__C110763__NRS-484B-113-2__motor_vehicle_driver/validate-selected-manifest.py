"""Run pinned selected CPU execution-manifest validation for this assignment."""
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parents[1]
sys.path.insert(0, str(repo / 'runtime/pipeline/scenario_pipeline'))
sys.path.insert(0, str(repo / 'runtime/pipeline'))
from scenario_pipeline.worker_exchange.execution_manifest import validate

validate(repo, folder.name)
print('selected_cpu_execution_manifest_validated 2')
