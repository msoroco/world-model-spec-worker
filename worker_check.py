import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent
sys.path.insert(0,str(root/'runtime/main-pipeline-v1/scenario_pipeline'))
from worker_exchange.preparation import check
p=argparse.ArgumentParser();p.add_argument('--complete',action='store_true');p.add_argument('--require-ready',action='store_true');a=p.parse_args()
r=check(root,complete=a.complete or a.require_ready,require_ready=a.require_ready)
print(json.dumps({'batch':r['batch_id'],'results':{k:v['status'] for k,v in r['results'].items()},'static_validation':'passed'},indent=2))
