"""Independent three-case source and 30-minute boundary isolation audit."""
import argparse
import json
from pathlib import Path

REQUESTS=(1500,1800,2100)

def require(ok,message):
    if not ok:raise ValueError(message)

def audit(attempts,tamper_context=False):
    paths=[Path(p) for p in attempts]
    require(len(paths)==3,'Exact three-case boundary comparison missing')
    contexts=[json.loads((p/'original_alley_context.json').read_text()) for p in paths]
    if tamper_context:contexts[2]['alley_polygon_xy_m'][0][0]-=1
    fixed_context_keys=set(contexts[0])-{'parking_ledger_sha256'}
    require(all(set(c)==set(contexts[0]) and all(c[k]==contexts[0][k] for k in fixed_context_keys) for c in contexts),
            'Fixed original alley/vehicle/lawful source changed')
    configs=[json.loads((p/'config.json').read_text()) for p in paths]
    fixed_config_keys=set(configs[0])-{'case_id','selected_case_id','requested_parked_seconds_in_rolling_hour'}
    require(all(set(c)==set(configs[0]) and all(c[k]==configs[0][k] for k in fixed_config_keys) for c in configs),
            'Fixed Native capture configuration changed')
    require(tuple(c['requested_parked_seconds_in_rolling_hour'] for c in configs)==REQUESTS,
            'Requested 25/30/35-minute boundary contrast changed')
    ledgers=[json.loads((p/'original_parking_ledger.json').read_text()) for p in paths]
    require(all(l['span_start_s']==0 and l['span_end_s']==3600 and
                len(l['parked_intervals'])==1 and l['parked_intervals'][0]['vehicle_id']==contexts[0]['vehicle_id']
                for l in ledgers),'One-hour source span or vehicle identity changed')
    findings=[json.loads((p/'analysis-report.json').read_text())['measurements']['alley_duration']['value'] for p in paths]
    require(tuple(f['max_parked_seconds_in_sourced_rolling_hour'] for f in findings)==REQUESTS,
            'Measured rolling-hour durations do not straddle 30-minute boundary')
    require(tuple(f['measured_greater_than_30_minutes'] for f in findings)==(False,False,True),
            'Strict greater-than-thirty boundary changed')
    require(all(f['legal_compliance']=='unassessed' for f in findings),
            'Comparison fabricated a legal verdict')
    return {'comparison_id':'alley_rolling_hour_30_minute_boundary',
            'requested_seconds':list(REQUESTS),'measured_seconds':list(REQUESTS),
            'strictly_greater_than_30':[False,False,True],
            'fixed_source_context':'same alley, vehicle and otherwise-lawful source; only separate hour ledger interval differs',
            'synthetic_cpu_diagnostic_only':True,'physical_or_legal_acceptance_claimed':False}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--low',required=True);parser.add_argument('--at',required=True);parser.add_argument('--high',required=True);parser.add_argument('--tamper-context',action='store_true')
    x=parser.parse_args();print(json.dumps(audit([x.low,x.at,x.high],x.tamper_context),sort_keys=True))
