"""Independently audit current synthetic compatibility and controlled pairs."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CAMERAS=('overview','approach','reference_corner','driver_reference')
CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def output(suffix,candidate):
    if candidate=='primary' and suffix=='reference':
        return ROOT/'.runtime-work/c10316-v15-reference-compat-primary-final'
    return ROOT/'.runtime-work'/('c10316-v15-'+suffix+'-compat-'+candidate)


def main():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    plan=json.loads((HERE/'case-plan.json').read_text())
    assert len(manifest['cases'])==2 and len(plan['comparisons'])==1
    comparison=plan['comparisons'][0]
    assert comparison['deliberate_differences']==['pedestrian_lateral_crosswalk_half']
    assert comparison['case_ids']==[item['case_id'] for item in manifest['cases']]
    proofs=[]
    for candidate in CANDIDATES:
        controlled=[]
        for suffix,entry in zip(('reference','contrast'),manifest['cases']):
            target=output(suffix,candidate)
            selected=entry if candidate=='primary' else next(
                x for x in entry['candidates'] if x['id']==candidate)
            receipt=json.loads((target/'compatibility.json').read_text())
            assert receipt['format']=='worker-package-compatibility' and receipt['passed'] is True
            assert receipt['case_id']==entry['case_id'] and receipt['candidate_id']==candidate
            assert receipt['construction_sha256']==selected['construction_sha256']==sha(HERE/selected['construction'])
            assert receipt['runtime_manifest_sha256']==manifest['runtime_manifest_sha256']
            assert {'selected_measurements','negative_case_source','derived_outputs_rebuilt',
                    'four_camera_sources','lean_decoder','final_decode'}<=set(receipt['checks'])
            assert receipt['analysis_sha256']==sha(target/'finalize.py')
            assert receipt['log_sha256']==sha(target/'compatibility-analysis.log')
            assert receipt['negative_log_sha256']==sha(target/'negative-analysis.log')
            assert receipt['negative_error_contains'] in (target/'negative-analysis.log').read_text()
            assert receipt['negative_removed']=='native_samples.jsonl'
            config=json.loads((target/'config.json').read_text())
            assert tuple(x['name'] for x in config['cameras'])==CAMERAS
            assert (target/'four-view-receipt.json').is_file()
            assert not any(name.startswith('channels/') for name in receipt['fixture_manifest'])
            for name in CAMERAS:
                assert sha(target/(name+'.mkv'))==receipt['fixture_manifest'][name+'.mkv']
            sample=rows(target/'native_samples.jsonl')
            position=rows(target/'channels/kin.position.jsonl')
            heading=rows(target/'channels/kin.heading.jsonl')
            assert len(sample)==len(position)==len(heading)==240
            assert all(p['value']==s['pedestrian_xy_m'] and
                       h['value']==s['pedestrian_forward_xy']
                       for s,p,h in zip(sample,position,heading))
            result=json.loads((target/'result.json').read_text())
            assert result['accepted'] is False and result['legal_verdict_claimed'] is False
            assert result['provenance_kind']=='synthetic_local_diagnostic'
            scenes=json.loads((target/'converted/trace.json').read_text())['scenes']
            assert len(scenes)==240
            assert json.loads((target/'final-decode.json').read_text())['passed'] is True
            controlled.append((config,scenes))
            proofs.append({'case_id':entry['case_id'],'candidate_id':candidate,
                           'receipt_sha256':sha(target/'compatibility.json'),
                           'negative_log_sha256':sha(target/'negative-analysis.log'),
                           'core_trace_sha256':sha(target/'converted/trace.json'),
                           'result_sha256':sha(target/'result.json'),
                           'frames':len(scenes),'original_acceptance_claimed':False})
        left,right=controlled
        a,b=(dict(item[0]) for item in controlled)
        for config in (a,b):
            for key in ('case_id','selected_case_id','case_suffix','candidate_id','case'):
                config.pop(key,None)
        assert a==b
        for reference,contrast in zip(left[1],right[1]):
            assert reference['t']==contrast['t']
            assert reference['structures']==contrast['structures']
            assert reference['env']==contrast['env']
            first=next(u['kin'] for u in reference['users'] if u['track']==107)
            second=next(u['kin'] for u in contrast['users'] if u['track']==107)
            assert abs(first['position'][0]-second['position'][0])<1e-9
            assert abs(first['position'][1]-second['position'][1]-1.3)<1e-9
            assert first['heading']==second['heading']
    report={'format':'c10316-current-synthetic-comparison-audit',
            'manifest_sha256':sha(HERE/'draft-execution-manifest.json'),
            'comparison_id':comparison['comparison_id'],
            'fixed_conditions_checked':comparison['fixed_conditions'],
            'deliberate_differences_checked':comparison['deliberate_differences'],
            'controlled_core_lateral_shift_m':1.3,
            'checked_pairs':4,'proofs':proofs,
            'scope':'unselected synthetic software proof; no physical or legal acceptance'}
    (HERE/'update015-exact-package-audit.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'passed':True,'compatibility_receipts':len(proofs),'checked_pairs':4}))


if __name__=='__main__':main()
