"""Review exact fallback deltas and comparison isolation for all delivery cases."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    reviewed=[];failures=[]
    for folder in sorted((ROOT/'work').glob('testing__*')):
        path=folder/'execution-manifest.json'
        if not path.is_file():continue
        manifest=json.loads(path.read_text())
        plan=json.loads((folder/'case-plan.json').read_text())
        linked={cid for comparison in plan['comparisons'] for cid in comparison['case_ids']}
        for entry in manifest['cases']:
            cid=entry['case_id']
            try:
                assert cid in linked, 'not in controlled comparison'
                assert len(entry['candidates'])==1 and entry['candidates'][0]['id']=='fallback1'
                fallback=entry['candidates'][0]
                assert fallback['trigger']['source']=='capture/evidence.jsonl'
                assert fallback['trigger']['metric']=='first_second_subject_vertical_centroid_range_m'
                assert fallback['trigger']['failure_condition']=='value_m > 0.05'
                assert fallback['trigger']['script_sha256']==sha(ROOT/'work/_shared/fallback_trigger.py')
                assert 'fallback_trigger.py' in fallback['trigger']['command']
                assert sha(folder/fallback['construction'])==fallback['construction_sha256']
                primary=json.loads((folder/entry['construction']).read_text())
                candidate=json.loads((folder/fallback['construction']).read_text())
                assert primary['recording_description']==candidate['recording_description']
                assert primary['case_id']==candidate['case_id']==cid
                assert primary['cell_id']==candidate['cell_id'] and primary['actor']==candidate['actor']
                a={f['path']:f['content'] for f in primary['files']}
                b={f['path']:f['content'] for f in candidate['files']}
                for artifact in candidate['files']:
                    source=artifact.get('source')
                    if source:
                        assert (ROOT/source).read_text()==artifact['content'], 'fallback source differs from inline bundle'
                assert set(a)==set(b)
                assert a['config.json']==b['config.json']
                assert {name for name in a if a[name]!=b[name]}=={'runner.py','tests/test_case.py'}
                old=20 if 'for _ in range(20):\n            world.tick()' in a['runner.py'] else 30
                assert f'for _ in range({old}):\n            world.tick()' in a['runner.py']
                expected=a['runner.py'].replace('def check():',
                    f'def startup_settling_ticks():\n    return {old+20}\n\ndef check():',1).replace(
                    f'for _ in range({old}):\n            world.tick()',
                    'for _ in range(startup_settling_ticks()):\n            world.tick()',1)
                assert b['runner.py']==expected, 'runner delta is not exclusively stationary warmup'
                assert 'StartupSettlingFallbackTest' in b['tests/test_case.py']
                assert fallback['offline']['exit_code']==0 and fallback['compatibility']['receipt']
                reviewed.append(cid)
            except (AssertionError,KeyError,ValueError) as error:
                failures.append({'case_id':cid,'error':str(error) or type(error).__name__})
    result={'format':'worker-candidate-review-v1','reviewed_cases':len(reviewed),
            'failed_cases':failures,'comparison_isolation':'config, recording description, and all comparison variables byte-identical; only pre-capture stationary Native warmup and its test differ',
            'physical_trigger':'first 20 original subject body-centroid z samples, >0.05 m',
            'legal_scope':'No legal threshold or outcome selects the fallback'}
    print(json.dumps(result,indent=2))
    if failures:raise SystemExit(1)
if __name__=='__main__':main()
