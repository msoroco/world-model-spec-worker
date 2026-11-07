"""Independent CPU audit that all exact drafts embed the tested source evaluator."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
NAMES=('primary','fallback1','fallback2','fallback3')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    code=(HERE/'native/fallback_triggers.py').read_text()
    tests=(HERE/'native/test_fallback_triggers.py').read_text()
    checked=[]
    for case in manifest['cases']:
        for name in NAMES:
            candidate=case if name=='primary' else next(c for c in case['candidates'] if c['id']==name)
            path=HERE/candidate['construction']
            assert sha(path)==candidate['construction_sha256']
            bundle=json.loads(path.read_text())
            files={f['path']:f['content'] for f in bundle['files']}
            assert files['fallback_triggers.py']==code
            assert files['tests/test_fallback_triggers.py']==tests
            log=HERE/'draft-candidates'/case['case_id'].split('__')[-1]/name/'unit-test.log'
            assert 'Ran 21 tests' in log.read_text() and '\nOK\n' in log.read_text()
            checked.append([case['case_id'],name,candidate['construction_sha256']])
    assert len(checked)==20
    result={'passed':True,'bundles':checked,'source_evaluator_sha256':sha(HERE/'native/fallback_triggers.py'),
            'scope':'embedded synthetic trigger logic and source-binding only; no original Native or pixel observation'}
    (HERE/'fallback-trigger-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps({'passed':audit()['passed'],'bundles':20}))
