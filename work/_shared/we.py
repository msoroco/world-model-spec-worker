"""Short path to the local worker-exchange CLI for queue command rows."""
import runpy
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(repo/'runtime/pipeline/scenario_pipeline'))
runpy.run_module('worker_exchange', run_name='__main__')
