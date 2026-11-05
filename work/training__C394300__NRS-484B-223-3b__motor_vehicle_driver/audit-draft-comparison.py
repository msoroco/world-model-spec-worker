"""Independent same-cell audit of five authored distance probes per candidate."""
import hashlib
import json
from pathlib import Path
import sys

FOLDER=Path(__file__).resolve().parent
sys.path.insert(0,str(FOLDER/'native'))
from engineering import parameters
from geometry import TARGET_FEET


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((FOLDER/'draft-execution-manifest.json').read_text())
    assert [e['case_id'].split('__')[-1] for e in manifest['cases']]==list(TARGET_FEET)
    checked=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        refs=[entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
              for entry in manifest['cases']]
        bundles=[json.loads((FOLDER/r['construction']).read_text()) for r in refs]
        files=[{f['path']:f['content'] for f in bundle['files']} for bundle in bundles]
        assert all(sha(FOLDER/r['construction'])==r['construction_sha256'] for r in refs)
        assert all(set(f)==set(files[0]) for f in files)
        assert all(all(f[name]==files[0][name] for name in files[0] if name!='config.json') for f in files)
        configs=[json.loads(f['config.json']) for f in files]
        permitted={'case_id','selected_case_id','supported_case_ids','case_suffix','case'}
        assert all(all(c[key]==configs[0][key] for key in configs[0] if key not in permitted) for c in configs)
        assert all(b['recording_description']==bundles[0]['recording_description'] for b in bundles)
        plans=[parameters(suffix,candidate) for suffix in TARGET_FEET]
        fixed=('law_id','cell_id','actor','duration_s','rate_hz','controller_knobs',
               'cameras','route_start_x_m','requested_movement')
        assert all(all(p[k]==plans[0][k] for k in fixed) for p in plans)
        assert len({p['comparison_commanded_distance_ft'] for p in plans})==5
        assert len({tuple(tuple(x) for x in p['native_route_xy_m']) for p in plans})==5
        checked.append(candidate)
    print(json.dumps({'passed':True,'case_count':5,'candidate_policies':checked,
        'fixed':'law/cell/actor/map source/controller/camera/rate/duration/recording contract',
        'deliberate_difference':'nominal lane-change station for 180, 199, 200, 201, and 220 foot requests',
        'scope':'authored CPU constructions only; measured Native distance and saved comparison pending'}))


if __name__=='__main__':main()
