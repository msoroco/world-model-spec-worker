"""Portable launcher. All implementation comes from the versioned main export."""
import sys
from pathlib import Path
if 'overlay' in sys.modules:
    raise ValueError('Runtime bootstrap override is unsupported')
from overlay import effective_runtime
root=effective_runtime()
sys.path.insert(0,str(root/'scenario_pipeline'))
sys.path.insert(1,str(root/'python'))
from worker_exchange.common import read,sha
batch=read(root.parents[1]/'batch.json')
if batch['runtime']['source_manifest_sha256']!=sha(Path(__file__).resolve().parent/batch['runtime']['root']/'SOURCE-MANIFEST.json'):raise ValueError('Runtime version mismatch')
from worker_exchange.runtime_cli import main
if __name__=='__main__':main()
