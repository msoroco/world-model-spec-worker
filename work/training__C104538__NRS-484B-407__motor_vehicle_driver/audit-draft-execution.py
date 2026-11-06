"""Independent exact-source, fallback and offline receipt audit for unselected drafts."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent
SHA=lambda path:hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    manifest=json.loads((ROOT/'draft-execution-manifest.json').read_text())
    offline=json.loads((ROOT/'draft-offline-summary.json').read_text())
    assert offline['manifest_sha256']==SHA(ROOT/'draft-execution-manifest.json')
    assert len(manifest['cases'])==3 and len(offline['rows'])==12
    passed=0;negatives=0
    for case in manifest['cases']:
        suffix=case['case_id'].split('__')[-1]
        candidates=[{'id':'primary','construction':case['construction'],
                     'construction_sha256':case['construction_sha256']}]+case['candidates']
        assert [row['id'] for row in candidates]==['primary','fallback1','fallback2','fallback3']
        assert len({row['construction_sha256'] for row in candidates})==4
        for item in candidates:
            assert SHA(ROOT/item['construction'])==item['construction_sha256']
            construction=json.loads((ROOT/item['construction']).read_text())
            files={entry['path']:entry['content'] for entry in construction['files']}
            config=json.loads(files['config.json'])
            assert construction['case_id']==case['case_id']==config['case_id']
            assert config['candidate_id']==item['id']
            assert files['authored_road.xodr']==(ROOT/'draft-sightline'/suffix/'road.xodr').read_text()
            assert files['obstruction.json']==(ROOT/'draft-sightline'/suffix/'obstruction.json').read_text()
            row=next(r for r in offline['rows'] if r['case_suffix']==suffix and r['candidate_id']==item['id'])
            assert row['exit_code']==0 and row['offline_log_sha256']==SHA(ROOT/row['offline_log'])
            assert 'OK' in (ROOT/row['offline_log']).read_text()
            if item['id']!='primary':
                assert all(item['trigger'].get(key) for key in ('source','metric','failure_condition'))
                assert len(item['changed_knobs'])==1
            passed+=1
        source=ROOT/'draft-offline-v9'/suffix/'primary'
        for name,damage,expected in (
            ('authored_road.xodr','damaged road','Materialized authored road differs'),
            ('obstruction.json','{}','Materialized obstruction differs')):
            with tempfile.TemporaryDirectory() as temporary:
                target=Path(temporary)/'package'
                shutil.copytree(source,target)
                (target/name).write_text(damage)
                result=subprocess.run(['python3.11',str(target/'runner.py'),'--check'],
                                      cwd=target,capture_output=True,text=True)
                assert result.returncode!=0 and expected in result.stderr
                negatives+=1
    return {'positive_exact_offline':passed,'damaged_source_rejections':negatives,
            'candidate_selection_count':0,'native_started':False}


if __name__=='__main__':print(json.dumps(audit()))
