"""Independent source and pinned-offline receipt audit for C422978 bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    manifest = read(HERE / 'draft-execution-manifest.json')
    summary = read(HERE / 'draft-offline-summary.json')
    assert manifest['status'] == 'draft_not_selected' and len(manifest['cases']) == 2
    assert len(summary['results']) == 8
    source = {
        'runner.py': (HERE / 'native/runner.py').read_text(),
        'triggers.py': (HERE / 'native/triggers.py').read_text(),
        'road.xodr': (HERE / 'native/road.xodr').read_text(),
        'assignment-source.json': (ROOT / 'inputs' / HERE.name / 'assignment.json').read_text(),
    }
    audited = []
    for case in manifest['cases']:
        suffix = case['case_id'].split('__')[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            ref = case if candidate == 'primary' else next(
                c for c in case['candidates'] if c['id'] == candidate)
            construction_path = HERE / ref['construction']
            assert sha(construction_path) == ref['construction_sha256']
            construction = read(construction_path)
            assert construction['case_id'] == case['case_id']
            assert construction['status'] == 'unselected_cpu_draft'
            files = {item['path']: item['content'] for item in construction['files']}
            assert len(files) == len(construction['files']) == 7
            for name, content in source.items(): assert files[name] == content
            config = json.loads(files['config.json'])
            assert config['case_id'] == case['case_id']
            assert config['candidate_id'] == candidate
            assert files['requested-tracks.jsonl'] == (
                HERE / 'native/drafts' / suffix / candidate / 'requested-tracks.jsonl').read_text()
            assert hashlib.sha256(files['requested-tracks.jsonl'].encode()).hexdigest() == config['tracks_sha256']
            receipt = read(HERE / 'draft-candidates' / suffix / candidate / 'draft-receipt.json')
            assert receipt['construction_sha256'] == ref['construction_sha256']
            assert receipt['case_id'] == case['case_id'] and receipt['candidate_id'] == candidate
            assert receipt['exit_code'] == 0
            assert receipt['command'][1] == str(ROOT / 'runtime.py')
            assert receipt['command'][2] == 'offline'
            assert receipt['command_log_sha256'] == sha(HERE / receipt['command_log'])
            assert receipt['unit_log_sha256'] == sha(HERE / receipt['unit_log'])
            log = (HERE / receipt['unit_log']).read_text()
            assert 'Ran 3 tests' in log and 'OK' in log
            assert 'simulation_started": false' in (HERE / receipt['command_log']).read_text().lower()
            assert not construction.get('physical_success_claimed', False)
            audited.append({'case_id': case['case_id'], 'candidate_id': candidate,
                            'construction_sha256': ref['construction_sha256']})
    output = {'format': 'c422978-independent-offline-audit-v1',
              'manifest_sha256': sha(HERE / 'draft-execution-manifest.json'),
              'summary_sha256': sha(HERE / 'draft-offline-summary.json'),
              'rows': audited, 'physical_or_delivery_acceptance_claimed': False}
    (HERE / 'draft-offline-audit.json').write_text(json.dumps(output, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(json.dumps({'audited': len(audit()['rows'])}))
