"""Independent controlled numeric CPU package comparison; no legal verdict."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def config(construction):
    return json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))


def main():
    manifest=json.loads((HERE/'draft-numeric-execution-manifest.json').read_text())
    if len(manifest['cases'])!=3:
        raise ValueError('Below, at and above probes required')
    source=json.loads((HERE/'synthetic-saved-proof.log').read_text())
    expected={'numeric_1_0':('within_15_ft',3.9),
              'numeric_1_1':('boundary_unresolved',4.572),
              'numeric_1_2':('outside_15_ft',5.4)}
    rows=[];fixed=[]
    for entry in manifest['cases']:
        validate(HERE,entry,'LVMC-11-52-130-A11','C110454',required=False,
                 require_alternate=True,candidate_count=4)
        suffix=entry['case_id'].split('__')[-1]
        if suffix not in expected:
            raise ValueError('Numeric case identity differs')
        relation,distance=expected[suffix]
        measured=source['results'][suffix]
        if measured['sampled_relation']!=relation or abs(measured['nearest_parked_body_distance_m']-distance)>.001:
            raise ValueError('Numeric saved measurement differs')
        if measured['rest_frames']!=80 or measured['native_physical_observation_claimed'] is not False:
            raise ValueError('Numeric source scope differs')
        contract=json.loads((HERE/entry['measurement_contract']).read_text())
        if contract['case_id']!=entry['case_id'] or contract['output_key']!='parked_body_distance_and_rest_interval':
            raise ValueError('Numeric contract identity differs')
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            selected=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            path=HERE/selected['construction'];folder=path.parent
            if sha(path)!=selected['construction_sha256']:
                raise ValueError('Numeric construction changed')
            construction=json.loads(path.read_text());cfg=config(construction)
            held={k:cfg[k] for k in ('cell_id','law_id','actor','rate_hz','duration_s',
                                     'required_atoms','source_packets','mandatory_channels',
                                     'recording_description','cameras','engineering_knobs')}
            fixed.append((candidate,held))
            offline=json.loads((folder/'command-offline.log').read_text())
            if offline['offline_passed'] is not True or offline['candidate_id']!=candidate or (
                offline['case_id']!=entry['case_id']):
                raise ValueError('Numeric exact offline proof differs')
            if 'Ran 10 tests' not in (folder/'offline.log').read_text():
                raise ValueError('Numeric bundle tests incomplete')
            runner=next(f['content'] for f in construction['files'] if f['path']=='runner.py')
            if 'observed_speed=observed_speed_mps(ego)' not in runner or (
                '"speed_mps":observed_speed' not in runner or
                '"speed_m_s":observed_speed' not in runner):
                raise ValueError('Numeric Native speed is not in the observed frame')
            receipt=json.loads((folder/'diagnostic-compatibility.json').read_text())
            if receipt['format']!='worker-package-compatibility-v1' or receipt['passed'] is not True or (
                receipt['case_id']!=entry['case_id'] or receipt['candidate_id']!=candidate or
                receipt['construction_sha256']!=selected['construction_sha256']):
                raise ValueError('Numeric exact compatibility receipt differs')
            if sha(folder/'analysis-compatibility.log')!=receipt['log_sha256'] or (
                'Missing required source: native_parking_history.json' not in
                (folder/'negative-analysis.log').read_text()):
                raise ValueError('Numeric positive/negative source proof differs')
            rows.append({'case_id':entry['case_id'],'candidate':candidate,
                         'construction_sha256':selected['construction_sha256'],
                         'receipt_sha256':sha(folder/'diagnostic-compatibility.json')})
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        values=[held for name,held in fixed if name==candidate]
        if len(values)!=3 or values[1:]!=values[:-1]:
            raise ValueError('Numeric comparison changed a held construction setting')
    if len(rows)!=12 or len({r['construction_sha256'] for r in rows})!=12:
        raise ValueError('Twelve distinct exact numeric candidates required')
    print(json.dumps({'format':'lvmc-numeric-independent-package-comparison-v1',
        'passed':True,'candidate_count':12,'rows':rows,
        'sampled_distances_m':{k:v[1] for k,v in expected.items()},
        'exact_boundary_relation':'boundary_unresolved',
        'scope':'authored/synthetic CPU comparison and v1 compatibility; no physical or legal conclusion'},indent=2))


if __name__=='__main__':main()
