"""Run the source-hashed portable runtime shipped with this batch."""
import sys
import os
import hashlib
from pathlib import Path
root=Path(__file__).resolve().parent
runtime=root/'runtime'
operation=hashlib.sha256('\0'.join(sys.argv[1:]).encode()).hexdigest()
private=(root/'.runtime-work').resolve()
configured=os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT')
output=(Path(configured).expanduser().resolve() if configured else private/'adapter'/operation)
if output != private and private not in output.parents:
    raise ValueError('Worker output root must be under '+str(private))
os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']=str(output)
sys.path.insert(0,str(runtime/'scenario_pipeline'))
sys.path.insert(1,str(runtime/'python'))
from worker_exchange.common import read,sha
# Shared adapter caches/manifests must never be written into frozen runtime/.
batch=read(root/'batch.json')
if batch['runtime']['source_manifest_sha256']!=sha(runtime/'SOURCE-MANIFEST.json'):
    raise ValueError('Runtime source manifest mismatch')
from worker_exchange.runtime_cli import main
if __name__=='__main__':main()
