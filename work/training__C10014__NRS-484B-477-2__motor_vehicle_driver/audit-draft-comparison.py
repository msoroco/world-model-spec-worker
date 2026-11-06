"""Audit exact shared inputs and the sole commanded stop-location difference."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from engineering import parameters


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    a,b=manifest['cases']
    assert a['case_id'].endswith('__reference') and b['case_id'].endswith('__contrast')
    reviewed=[]
    for candidate in ('primary','fallback1','fallback2','fallback3'):
        refs=[entry if candidate=='primary' else next(c for c in entry['candidates'] if c['id']==candidate)
              for entry in (a,b)]
        bundles=[json.loads((HERE/r['construction']).read_text()) for r in refs]
        files=[{item['path']:item['content'] for item in bundle['files']} for bundle in bundles]
        assert all(sha(HERE/r['construction'])==r['construction_sha256'] for r in refs)
        assert set(files[0])==set(files[1])
        assert all(files[0][name]==files[1][name] for name in files[0] if name!='config.json')
        configs=[json.loads(f['config.json']) for f in files]
        permitted={'case_id','selected_case_id','supported_case_ids','case_suffix','case'}
        assert all(configs[0][key]==configs[1][key] for key in configs[0] if key not in permitted)
        plans=[parameters(suffix,candidate) for suffix in ('reference','contrast')]
        assert all(plans[0][key]==plans[1][key] for key in plans[0] if key!='stop_x_m')
        assert plans[0]['stop_x_m']==-12 and plans[1]['stop_x_m']==0
        assert bundles[0]['recording_description']==bundles[1]['recording_description']
        reviewed.append(candidate)
    result={'passed':True,'candidate_policies':reviewed,
            'held':'law/cell/actor/map source/approach/braking/cameras/rate/duration/recording contract',
            'deliberate_difference':'requested stationary x coordinate -12 m versus 0 m',
            'physical_verified':False,'selected':False}
    print(json.dumps(result))
    return result


if __name__=='__main__':audit()
