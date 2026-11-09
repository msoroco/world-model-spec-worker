"""Run the source-hashed portable runtime shipped with this batch."""
import sys
from pathlib import Path
root=Path(__file__).resolve().parent
runtime=root/'runtime'
sys.path.insert(0,str(runtime/'scenario_pipeline'))
sys.path.insert(1,str(runtime/'python'))
from worker_exchange.common import read,sha
batch=read(root/'batch.json')
if batch['runtime']['source_manifest_sha256']!=sha(runtime/'SOURCE-MANIFEST.json'):
    raise ValueError('Runtime source manifest mismatch')
from worker_exchange.runtime_cli import main
if __name__=='__main__':main()
