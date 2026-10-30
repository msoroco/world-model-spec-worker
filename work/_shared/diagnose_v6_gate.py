"""Read-only diagnostic: patch one pinned baseline-ID comparison in memory."""
import inspect
import json
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'runtime/main-pipeline-v6/scenario_pipeline'))
import worker_exchange.preparation as preparation
source=inspect.getsource(preparation.check)
old="{c.get('case_id') for c in proposal['cases']}==ids"
new="{c.get('case_id') for c in proposal['cases'] if c.get('target_type')!='baseline'}==ids"
assert source.count(old)==1
namespace={}
exec(source.replace(old,new),preparation.__dict__,namespace)
original=preparation.read
def read(path):
    value=original(path)
    if str(path).endswith('/result.json') and '/work/' in str(path):
        value=dict(value,status='ready',readiness_kind='delivery_prepared')
    return value
preparation.read=read
result=namespace['check'](ROOT,complete=True,require_ready=True)
print(json.dumps({'diagnostic_passed':True,'packages':len(result['results']),
                  'patch':'exclude canonical neutral baseline from selected case-plan comparison only',
                  'official_gate_passed':False},indent=2))
