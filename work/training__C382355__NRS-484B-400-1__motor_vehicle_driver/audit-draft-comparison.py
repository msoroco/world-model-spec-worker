"""Controlled-input comparison audit; saved physical comparison remains pending."""
import hashlib
import json
from pathlib import Path
import sys

FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(FOLDER/'native'))
from engineering import parameters


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
    a,b=manifest['cases']
    assert a['case_id'].endswith('witness_1') and b['case_id'].endswith('witness_2')
    checked=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        refs=[entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
              for entry in (a,b)]
        bundles=[json.loads((FOLDER/r['construction']).read_text()) for r in refs]
        files=[{f['path']:f['content'] for f in bundle['files']} for bundle in bundles]
        assert all(sha(FOLDER/r['construction'])==r['construction_sha256'] for r in refs)
        assert set(files[0])==set(files[1])
        assert all(files[0][name]==files[1][name] for name in files[0] if name!='config.json')
        configs=[json.loads(f['config.json']) for f in files]
        permitted={'case_id','selected_case_id','supported_case_ids','case_suffix','case'}
        assert all(configs[0][key]==configs[1][key] for key in configs[0] if key not in permitted)
        assert bundles[0]['recording_description']==bundles[1]['recording_description']
        plans=[parameters(suffix,candidate) for suffix in ('witness_1','witness_2')]
        for key in ('law_id','cell_id','actor','duration_s','rate_hz','controller_knobs','cameras','turn_entry_x_m'):
            assert plans[0][key]==plans[1][key],(candidate,key)
        assert plans[0]['comparison_approach_y_m']==-5.25 and plans[1]['comparison_approach_y_m']==-1.75
        assert plans[0]['native_route_xy_m']!=plans[1]['native_route_xy_m']
        checked.append(candidate)
    print(json.dumps({'passed':True,'candidate_policies':checked,
        'held':'law/cell/actor/map source/controller/camera/rate/duration/recording contract',
        'deliberate_difference':'requested right-turn approach lane',
        'scope':'authored CPU constructions only; realized Native and saved-pixel comparison pending'}))


if __name__=='__main__':main()
