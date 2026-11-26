"""Bind selected hose proof chain, Native acquisition and recorded-only processing."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_way_hose_protection_and_command_review'
    mapping = {
        'st.obstruction': ('original hose placement and independent asset/protection inventory', ['hose-source.json', 'hose-review.json', 'reference_corner.mkv']),
        'rel.occupies': ('original full-body footprint against reviewed hose geometry', ['actor-sources.jsonl', 'hose-source.json']),
        'kin.path_length': ('original per-frame vehicle center trajectory', ['actor-sources.jsonl']),
        'st.highway': ('original road and independent dedication/access review', ['road.xodr', 'way-review.json']),
        'ru.fire_apparatus': ('original apparatus/command-role actor and department affiliation and specified use purpose independently reviewed', ['department-presence.json', 'hose-source.json', 'hose-review.json']),
        'dev.human_direction': ('authored explicit communication setup and independent command identity/status, consent or no-communication review', ['communication-setup.json', 'command-review.json']),
        'kin.velocity': ('original actor speed and driver identity', ['actor-sources.jsonl', 'command-review.json'])}
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        proof = HERE / 'proofs' / suffix
        entry['physical_preparation'] = {'receipt': str((proof / 'physical-preparation.json').relative_to(HERE)),
                                         'sha256': sha(proof / 'physical-preparation.json')}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {name: {'entrypoint': 'runner.py', 'method': method, 'evidence': evidence}
                                for name, (method, evidence) in mapping.items()}
        entry['post_capture'] = {'recorded_only': True,
            'command': 'runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + entry['case_id'] +
                ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/feedback.json # ' + entry['case_id']}
        if (proof / 'saved.log').is_file():
            entry['post_capture'].update(test_log=str((proof / 'saved.log').relative_to(HERE)),
                test_log_sha256=sha(proof / 'saved.log'), test_exit_code=0)
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    first = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    for item in first['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    (HERE / 'construction.json').write_text(json.dumps(first, indent=2) + '\n')
    print({'cases': len(manifest['cases']), 'fallbacks': sum(len(row['candidates']) for row in manifest['cases'])})


if __name__ == '__main__':
    main()
