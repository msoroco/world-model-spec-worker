"""Independent exception alternative comparison across exact unselected bundles."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from xml.etree import ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT/'runtime/pipeline/scenario_pipeline'))
from worker_exchange.candidate_constructions import validate

BRANCHES={
    'exception_1_1':('necessary_traffic_conflict','absent'),
    'exception_1_2':('necessary_traffic_conflict','present'),
    'exception_2_1':('compliance_with_law','absent'),
    'exception_2_2':('compliance_with_law','present'),
    'exception_3_1':('police_or_device_direction','absent'),
    'exception_3_2':('police_or_device_direction','present'),
}
CANDIDATES=('primary','fallback1','fallback2','fallback3')
TRIGGERS={'fallback1':'max_park_route_cross_track_error_m',
          'fallback2':'parked_endpoint_speed_m_s',
          'fallback3':'min_parked_ego_pixel_margin_px'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    manifest_path=HERE/'draft-exception-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if len(manifest['cases'])!=6:raise ValueError('Six statutory exception alternatives required')
    rows=[];held_by_candidate={candidate:[] for candidate in CANDIDATES}
    for entry in manifest['cases']:
        suffix=entry['case_id'].split('__')[-1]
        branch,polarity=BRANCHES[suffix]
        validate(HERE,entry,'LVMC-11-52-130-A11','C110454',required=False,
                 require_alternate=True,candidate_count=4)
        contract=json.loads((HERE/entry['measurement_contract']).read_text())
        if contract['case_id']!=entry['case_id'] or contract['output_key']!='exception_source_context' or (
            contract['negative']['remove']!=['exception_context.json']):
            raise ValueError('Exception measurement contract differs')
        for candidate in CANDIDATES:
            selected=entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
            path=HERE/selected['construction'];folder=path.parent
            if sha(path)!=selected['construction_sha256']:raise ValueError('Exception construction hash differs')
            construction=json.loads(path.read_text())
            cfg=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
            if cfg['case_id']!=entry['case_id'] or cfg['exception_branch']!=branch or cfg['requested_polarity']!=polarity:
                raise ValueError('Exception branch/case identity differs')
            if cfg['status']!='unselected_native_runner_prototype' or construction['status']!='unselected_cpu_draft':
                raise ValueError('Exception package incorrectly selected')
            if candidate!='primary':
                trigger=selected['trigger']
                if trigger['metric']!=TRIGGERS[candidate] or trigger['source']!='original Native pose and decoded source video':
                    raise ValueError('Exception fallback trigger is not source based')
            road=ET.fromstring(next(f['content'] for f in construction['files'] if f['path']=='road.xodr'))
            destination=next(r for r in road.findall('road') if r.attrib['id']=='2')
            signal_ids=[s.attrib['id'] for s in destination.find('signals').findall('signal')]
            expected_signal=['620'] if suffix in ('exception_2_2','exception_3_2') else []
            if signal_ids!=expected_signal:
                raise ValueError('Controlled device contrast differs from authored road')
            if bool(cfg.get('authored_device_source_id'))!=bool(expected_signal):
                raise ValueError('Device source ID differs from authored road')
            held={k:cfg[k] for k in ('cell_id','law_id','actor','rate_hz','duration_s',
                  'required_atoms','source_packets','mandatory_channels','recording_description','cameras')}
            held_by_candidate[candidate].append(held)
            offline=json.loads((folder/'command-offline.log').read_text())
            if not offline['offline_passed'] or offline['case_id']!=entry['case_id'] or offline['candidate_id']!=candidate:
                raise ValueError('Exact exception offline proof differs')
            expected_tests=11 if suffix in ('exception_2_2','exception_3_2') else 10
            if f'Ran {expected_tests} tests' not in (folder/'offline.log').read_text():
                raise ValueError('Exception bundle tests incomplete')
            receipt=json.loads((folder/'diagnostic-compatibility.json').read_text())
            if receipt['format']!='worker-package-compatibility-v1' or not receipt['passed'] or (
                receipt['case_id']!=entry['case_id'] or receipt['candidate_id']!=candidate or
                receipt['construction_sha256']!=selected['construction_sha256']):
                raise ValueError('Exact exception compatibility differs')
            if sha(folder/'analysis-compatibility.log')!=receipt['log_sha256'] or (
                'Missing required source: exception_context.json' not in (folder/'negative-analysis.log').read_text()):
                raise ValueError('Exception positive/negative source diagnostic differs')
            rows.append({'case_id':entry['case_id'],'candidate':candidate,
                'construction_sha256':selected['construction_sha256'],
                'receipt_sha256':sha(folder/'diagnostic-compatibility.json')})
    polarity=json.loads((HERE/'exception-absence-proof.json').read_text())
    if not polarity.get('passed') or len(polarity.get('rows',[]))!=6:
        raise ValueError('Six controlled exception polarity source proofs required')
    for row in polarity['rows']:
        if row['case_suffix'] not in BRANCHES or row['physical_observation_claimed'] is not False or row['legal_verdict'] is not None:
            raise ValueError('Exception polarity source proof claims physical or legal conclusion')
        if not row['controlled_negative_error'] or 'not joined' not in row['truncated_frame_negative_error']:
            raise ValueError('Exception polarity negatives incomplete')
    laws=json.loads((ROOT/'inputs/coverage/branch-sources.json').read_text())
    law_text=laws['laws']['NRS-484B-300-1']['law']['text']
    expected_digest=hashlib.sha256(law_text.encode()).hexdigest()
    source=(HERE/'native/exception_case.py').read_text()
    if expected_digest not in source:
        raise ValueError('Compliance source digest differs from frozen law')
    for candidate,values in held_by_candidate.items():
        if values[1:]!=values[:-1]:
            raise ValueError('Controlled exception comparison changed a held setting: '+candidate)
    if len(rows)!=24 or len({r['construction_sha256'] for r in rows})!=24:
        raise ValueError('Twenty-four distinct exact exception bundles required')
    return {'format':'lvmc-exception-independent-package-comparison-v1','passed':True,
        'manifest_sha256':sha(manifest_path),'candidate_count':24,'polarity_source_proofs':6,'rows':rows,
        'source_binding':{'compliance_cited_law':'NRS-484B-300-1',
          'device_video_sha_checked':True,'authored_device_road_signal_id':'620','conflict_actor_frame_join_checked':True},
        'scope':'source-bound synthetic CPU comparison; no CARLA behavior, physical trigger, legal applicability or accepted recording'}

if __name__=='__main__':
    print(json.dumps(main(),indent=2))
