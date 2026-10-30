import argparse,json,sys
from pathlib import Path
root=Path(__file__).resolve().parent
from overlay import effective_runtime
sys.path.insert(0,str(effective_runtime()/'scenario_pipeline'))
from worker_exchange.preparation import check
p=argparse.ArgumentParser();p.add_argument('--complete',action='store_true');p.add_argument('--require-ready',action='store_true');p.add_argument('--require-capability-ready',action='store_true');p.add_argument('--require-delivery-ready',action='store_true');a=p.parse_args()
if a.require_capability_ready and a.require_delivery_ready:p.error('Choose one readiness gate')
if a.require_capability_ready and json.loads((root/'batch.json').read_text()).get('delivery_handoff_required'):
    p.error('This batch requires --require-delivery-ready')
ready=a.require_ready or a.require_capability_ready or a.require_delivery_ready
r=check(root,complete=a.complete or ready,require_ready=ready)
if a.require_delivery_ready and not json.loads((root/'batch.json').read_text()).get('delivery_handoff_required'):
    p.error('Batch does not require a delivery handoff')
print(json.dumps({'batch':r['batch_id'],'results':{k:v['status'] for k,v in r['results'].items()},'static_validation':'passed'},indent=2))
