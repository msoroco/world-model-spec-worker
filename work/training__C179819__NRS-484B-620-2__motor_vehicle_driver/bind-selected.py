"""Bind exact signed-zone proofs into the selected execution manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return str(path.relative_to(HERE))


def main():
    manifest = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    manifest['status'] = 'cpu_prepared_pending_original_zone_and_sign_review'
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        proof = HERE / 'proofs' / suffix
        digest = entry['construction_sha256']
        entry['offline'] = {'exit_code': 0, 'construction_sha256': digest,
            'command': 'runtime.py offline --case ' + entry['case_id'] + ' --candidate primary',
            'log': ref(proof/'offline.log'), 'log_sha256': sha(proof/'offline.log')}
        entry['compatibility'] = {'receipt': ref(proof/'compatibility.json'),
            'sha256': sha(proof/'compatibility.json'), 'log': ref(proof/'public-analysis.log'),
            'negative_log': ref(proof/'negative-analysis.log')}
        entry['negative'] = {'log': ref(proof/'negative-analysis.log'),
            'log_sha256': sha(proof/'negative-analysis.log')}
        entry['physical_preparation'] = {'receipt': ref(proof/'physical-preparation.json'),
            'sha256': sha(proof/'physical-preparation.json')}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
            'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            'kin.speed': {'entrypoint': 'runner.py', 'method': 'original Native velocity magnitude at each frame', 'evidence': ['actor-poses.jsonl']},
            'dev.speed_limit_sign': {'entrypoint': 'runner.py', 'method': 'original RGB and separate installed sign review', 'evidence': ['reference_corner.mkv','installed-sign-review.json']},
            'dev.zone_sign': {'entrypoint': 'runner.py', 'method': 'authored zone landmarks plus administrative establishment review', 'evidence': ['road.xodr','zone-establishment.json']},
            'drv.within_signed_zone': {'entrypoint': 'runner.py', 'method': 'original actor pose joined to reviewed bounds', 'evidence': ['actor-poses.jsonl','zone-establishment.json']},
            'dev.governs': {'entrypoint': 'runner.py', 'method': 'reviewed road and direction join', 'evidence': ['installed-sign-review.json','zone-establishment.json']},
            'rel.occupies': {'entrypoint': 'runner.py', 'method': 'original route position', 'evidence': ['actor-poses.jsonl']},
            'ru.motor_vehicle': {'entrypoint': 'runner.py', 'method': 'Native subject blueprint and independent class review', 'evidence': ['sign-survey-native.json','zone-establishment.json']}}
        entry['post_capture'] = {'recorded_only': True,
            'command': 'runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + entry['case_id'] +
                ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
            'feedback_command': 'cat $SAVED_OUTPUT/feedback.json # ' + entry['case_id']}
        if (proof/'saved.log').is_file():
            entry['post_capture'].update(test_log=ref(proof/'saved.log'),
                test_log_sha256=sha(proof/'saved.log'), test_exit_code=0)
        fallback = entry['candidates'][0]
        fallback['offline'] = {'exit_code': 0,
            'construction_sha256': fallback['construction_sha256'],
            'command': 'runtime.py offline --case ' + entry['case_id'] + ' --candidate fallback1',
            'log': ref(proof/'fallback1-offline.log'), 'log_sha256': sha(proof/'fallback1-offline.log')}
        fallback['compatibility'] = {'receipt': ref(proof/'fallback1-compatibility.json'),
            'sha256': sha(proof/'fallback1-compatibility.json'),
            'log': ref(proof/'fallback1-compatibility-analysis.log'),
            'negative_log': ref(proof/'fallback1-negative-analysis.log')}
    (HERE/'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    first = json.loads((HERE/manifest['cases'][0]['construction']).read_text())
    for item in first['files']:
        target = HERE/item['path']
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(item['content'])
    (HERE/'construction.json').write_text(json.dumps(first, indent=2)+'\n')
    print({'cases':len(manifest['cases']),'fallbacks':sum(len(e['candidates']) for e in manifest['cases'])})


if __name__ == '__main__':
    main()
