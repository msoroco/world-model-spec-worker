"""Portable launcher. All implementation comes from the versioned main export."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parent/'runtime/main-pipeline-v1'
sys.path.insert(0,str(root/'scenario_pipeline'))
sys.path.insert(1,str(root/'python'))
from worker_exchange.common import read,sha
batch=read(root.parents[1]/'batch.json')
if batch['runtime']['source_manifest_sha256']!=sha(root/'SOURCE-MANIFEST.json'):raise ValueError('Runtime version mismatch')
from worker_exchange.runtime_cli import main
if __name__=='__main__':main()
