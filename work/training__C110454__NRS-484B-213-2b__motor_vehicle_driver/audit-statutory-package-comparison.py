"""Independent exact comparison of railroad and one-way unselected packages."""
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

CASES={
 'rail_reference':('railroad_crossing',False,'outside_100_ft'),
 'rail_contrast':('railroad_crossing',False,'within_100_ft'),
 'oneway_absent':('intersection',False,'within_100_ft'),
 'oneway_present':('intersection',True,'within_100_ft'),
}
CANDIDATES=('primary','fallback1','fallback2','fallback3')
TRIGGERS={'fallback1':'max_route_cross_track_error_m',
          'fallback2':'parking_endpoint_speed_m_s','fallback3':'min_ego_pixel_margin_px'}

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def main():
    manifest_path=HERE/'draft-statutory-execution-manifest.json'
    manifest=json.loads(manifest_path.read_text())
    if len(manifest['cases'])!=4:raise ValueError('Four railroad/one-way statutory cases required')
    saved=json.loads((HERE/'statutory-saved-proof.json').read_text())
    if not saved['passed'] or len(saved['results'])!=4:raise ValueError('Four saved source proofs required')
    measured={r['case_suffix']:r for r in saved['results']}
    source_contrasts=json.loads((HERE/'statutory-contrast-proof.json').read_text())
    if not source_contrasts.get('passed') or len(source_contrasts.get('rows',[]))!=4:
        raise ValueError('Four controlled statutory source negatives required')
    for row in source_contrasts['rows']:
        if row['case_suffix'] not in CASES or row['physical_observation_claimed'] is not False or row['legal_verdict'] is not None:
            raise ValueError('Statutory source proof claims physical or legal result')
        if not row['changed_context_negative'] or not row['changed_road_negative']:
            raise ValueError('Statutory context or authored road negative absent')
    rows=[];settings={candidate:[] for candidate in CANDIDATES}
    for entry in manifest['cases']:
        suffix=entry['case_id'].split('__')[-1]
        zone,one_way,relation=CASES[suffix]
        validate(HERE,entry,'NRS-484B-213-2b','C110454',required=False,
                 require_alternate=True,candidate_count=4)
        result=measured[suffix]
        if result['sampled_relation']!=relation or result['one_way']!=one_way or (
            result['railroad_crossing']!=(zone=='railroad_crossing')) or result['frames']!=480:
            raise ValueError('Saved statutory source relation differs')
        contract=json.loads((HERE/entry['measurement_contract']).read_text())
        if contract['case_id']!=entry['case_id'] or (
            contract['negative']['remove']!=['statutory_context.json']):
            raise ValueError('Statutory source contract differs')
        for candidate in CANDIDATES:
            selected=entry if candidate=='primary' else next(x for x in entry['candidates'] if x['id']==candidate)
            path=HERE/selected['construction'];folder=path.parent
            if sha(path)!=selected['construction_sha256']:raise ValueError('Statutory construction hash differs')
            construction=json.loads(path.read_text())
            runner=next(f['content'] for f in construction['files'] if f['path']=='runner.py')
            if ('observed_speed=observed_speed_mps(ego)' not in runner or
                '"speed_mps":observed_speed' not in runner or
                '"speed_m_s":observed_speed' not in runner):
                raise ValueError('Statutory Native saved speed is not observed after the tick')
            cfg=json.loads(next(f['content'] for f in construction['files'] if f['path']=='config.json'))
            road=ET.fromstring(next(f['content'] for f in construction['files'] if f['path']=='road.xodr'))
            rail=road.findall(".//object[@id='701']")
            approach=next(r for r in road.findall('road') if r.attrib['id']=='1')
            lanes=approach.find('lanes/laneSection')
            left={l.attrib['id'] for l in lanes.find('left').findall('lane')}
            right={l.attrib['id'] for l in lanes.find('right').findall('lane')}
            if bool(rail)!=(zone=='railroad_crossing') or (one_way and (left or right!={'-1','-2'})) or (
                not one_way and (left!={'1'} or right!={'-1'})):
                raise ValueError('Authored rail/one-way geometry contrast differs')
            if cfg['case_id']!=entry['case_id'] or cfg['status']!='unselected_native_runner_prototype':
                raise ValueError('Unselected statutory identity differs')
            if candidate!='primary' and selected['trigger']['metric']!=TRIGGERS[candidate]:
                raise ValueError('Measured fallback trigger differs')
            held={k:cfg[k] for k in ('cell_id','law_id','actor','duration_s','rate_hz',
                'source_packets','mandatory_channels','recording_description','cameras')}
            settings[candidate].append(held)
            offline=json.loads((folder/'command-offline.log').read_text())
            if not offline['offline_passed'] or offline['case_id']!=entry['case_id'] or offline['candidate_id']!=candidate:
                raise ValueError('Exact statutory offline receipt differs')
            if 'Ran 8 tests' not in (folder/'offline.log').read_text():
                raise ValueError('Exact statutory test count differs')
            receipt=json.loads((folder/'diagnostic-compatibility.json').read_text())
            if receipt['format']!='worker-package-compatibility-v1' or not receipt['passed'] or (
                receipt['construction_sha256']!=selected['construction_sha256'] or
                receipt['case_id']!=entry['case_id'] or receipt['candidate_id']!=candidate):
                raise ValueError('Exact statutory package compatibility differs')
            if sha(folder/'analysis-compatibility.log')!=receipt['log_sha256'] or (
                'Missing required source: statutory_context.json' not in (folder/'negative-analysis.log').read_text()):
                raise ValueError('Statutory positive/negative saved source differs')
            rows.append({'case_id':entry['case_id'],'candidate':candidate,
                'construction_sha256':selected['construction_sha256'],
                'receipt_sha256':sha(folder/'diagnostic-compatibility.json')})
    for candidate,held in settings.items():
        if held[1:]!=held[:-1]:raise ValueError('Controlled setting differs: '+candidate)
    if len(rows)!=16 or len({r['construction_sha256'] for r in rows})!=16:
        raise ValueError('Sixteen distinct statutory bundles required')
    return {'format':'c110454-213-independent-statutory-package-comparison-v1',
        'passed':True,'candidate_count':16,'manifest_sha256':sha(manifest_path),
        'saved_proof_sha256':sha(HERE/'statutory-saved-proof.json'),
        'source_contrast_sha256':sha(HERE/'statutory-contrast-proof.json'),'rows':rows,
        'scope':'authored and synthetic source comparison only; no physical railroad, one-way legal applicability, or accepted recording'}

if __name__=='__main__':print(json.dumps(main(),indent=2))
