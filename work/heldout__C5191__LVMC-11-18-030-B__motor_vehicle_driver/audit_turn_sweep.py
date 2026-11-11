"""Independent saved-original audit of the three exact turn excursion points."""
import hashlib
import json
from pathlib import Path
import shlex

from turn_finalizer import original_approach_fraction, rows

HERE=Path(__file__).resolve().parent
POINTS={'turn_excursion-0000':.2,'turn_excursion-0001':.6,'turn_excursion-0002':.4}
CAMERAS=('overview','approach','reference_corner','driver_reference')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())

def audit():
    manifest=read(HERE/'execution-manifest.json')
    canonical=read(HERE/'proposals/cases.json')
    spec=next(s for s in canonical['sweep_specs'] if s['sweep_id']=='turn_preparation_lawfulness_sweep')
    if spec['status']!='complete' or spec['selection_order']!=[manifest['assignment_id']+'__'+suffix for suffix in POINTS]:
        raise ValueError('Exact turn sweep order differs')
    fixed_context=None;fixed_cameras=None;results=[]
    for suffix,requested in POINTS.items():
        case=manifest['assignment_id']+'__'+suffix
        entry=next(e for e in manifest['cases'] if e['case_id']==case)
        construction=HERE/entry['construction']
        if sha(construction)!=entry['construction_sha256']:raise ValueError('Turn sweep construction changed')
        config=json.loads(next(f['content'] for f in read(construction)['files'] if f['path']=='config.json'))
        if config['engineering']['crossing_fraction']!=requested:raise ValueError('Turn sweep requested control changed')
        proof=read(HERE/(suffix+'-saved-proof.json'))
        if proof['construction_sha256']!=entry['construction_sha256'] or proof['manifest_sha256']!=sha(HERE/'execution-manifest.json'):
            raise ValueError('Turn sweep saved proof does not bind current construction/manifest')
        words=shlex.split(proof['command']);version=Path(words[words.index('--output')+1])/'v0001'
        if sha(version/'processing.json')!=proof['receipt_sha256']:raise ValueError('Turn sweep saved receipt changed')
        stage=version/'analysis';report=read(stage/'analysis-report.json');result=read(stage/'result.json')
        original=stage/'turn_originals.jsonl';samples=rows(original)
        expected_sha=report['measurements']['marked_turn_observation']['sources']['turn_originals.jsonl']
        if sha(original)!=expected_sha:raise ValueError('Turn sweep original source hash changed')
        fractions=[original_approach_fraction(row) for row in samples if row['approach_active']]
        observed=max(fractions)
        stream=rows(stage/'lane_crossing_fraction.jsonl')
        if len(stream)!=len(fractions) or any(abs(row['value']-value)>1e-9 for row,value in zip(stream,fractions)):
            raise ValueError('Turn sweep saved fraction stream changed')
        summary=result['realized_observables']['lane_crossing_fraction']
        if summary['unit']!='fraction' or summary['reference']!='lane_crossing_fraction.jsonl' or abs(summary['value']-observed)>1e-9:
            raise ValueError('Turn sweep summary changed')
        if abs(observed-requested)>1e-6:raise ValueError('Turn sweep diagnostic point did not realize source fraction')
        measurement=report['measurements']['marked_turn_observation']['value']
        if measurement['left_indicator_readback_frames']!=0 or measurement['observed_heading_change_deg']<45:
            raise ValueError('Turn sweep fixed turn/signal context changed')
        context=sha(stage/'turn_scene_context.json')
        cameras={name:sha(stage/(name+'.mkv')) for name in CAMERAS}
        if fixed_context is None:fixed_context=context;fixed_cameras=cameras
        elif context!=fixed_context or cameras!=fixed_cameras:raise ValueError('Turn sweep fixed route/camera source changed')
        results.append({'case_id':case,'requested_fraction':requested,'observed_diagnostic_fraction':observed,'minimum_diagnostic_clearance_m':measurement['minimum_approach_clearance_m'],'construction_sha256':entry['construction_sha256'],'saved_proof_sha256':sha(HERE/(suffix+'-saved-proof.json')),'original_source_sha256':expected_sha,'fraction_stream_sha256':sha(stage/'lane_crossing_fraction.jsonl'),'saved_result_sha256':sha(stage/'result.json')})
    if len({round(r['observed_diagnostic_fraction'],9) for r in results})!=len(POINTS):
        raise ValueError('Turn sweep diagnostic fractions did not separate')
    return {'format':'worker-C5191-turn-sweep-audit','sweep_id':spec['sweep_id'],'spec_version':spec['spec_version'],'fixed_route_sha256':fixed_context,'fixed_camera_sha256':fixed_cameras,'cases':results,'diagnostic_fraction_separation_established':True,'physical_fraction_separation_claimed':False,'lawful_turn_decided':False}

if __name__=='__main__':
    proof=audit();(HERE/'turn-sweep-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    print([(r['requested_fraction'],r['observed_diagnostic_fraction'],r['minimum_diagnostic_clearance_m']) for r in proof['cases']])
