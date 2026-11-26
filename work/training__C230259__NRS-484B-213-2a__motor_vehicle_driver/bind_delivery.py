"""Bind completed exact CPU proofs into the six-case delivery manifest."""
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
SCRATCH = REPO / '.runtime-work/nrs213-resume-5'
SUFFIXES = ('probe_a', 'probe_b', 'curve_right', 'curve_left',
            'one_way_crest', 'one_way_curve')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion',
          'independent_sight_and_hazard_review')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def copy(source, relative):
    target = HERE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    data = target.read_bytes()
    if data.endswith(b'\n\n') or any(line.rstrip(b' \t') != line for line in data.splitlines()):
        raise ValueError('Proof output has trailing whitespace: ' + relative)
    if len(data) > 2 * 1024 * 1024:
        raise ValueError('Proof output exceeds size limit: ' + relative)
    return {'path': relative, 'sha256': sha(target)}


def bind_proof(entry, candidate, suffix):
    selected = entry if candidate == 'primary' else entry['candidates'][0]
    case = entry['case_id']
    tail = ''
    offline_cmd = ('.venv-cpu/bin/python -B runtime.py offline --manifest work/' + AID +
                   ('/selected-construction-draft.json' if candidate == 'primary'
                    else '/selected-fallback-draft.json') +
                   ' --case ' + case + (' --candidate fallback1' if candidate == 'fallback1' else '') +
                   ' --output .runtime-work/nrs213-resume-5/offline-' +
                   candidate + '-' + suffix + tail + ' --python $PWD/.venv-cpu/bin/python')
    log = copy(SCRATCH / ('offline-' + candidate + '-' + suffix + tail + '.stdout'),
               'selected-proofs/' + candidate + '-' + suffix + '-offline.log')
    selected['offline'] = {'case_id': case, 'candidate_id': candidate,
                           'construction_sha256': selected['construction_sha256'],
                           'command': offline_cmd, 'exit_code': 0,
                           'log': log['path'], 'log_sha256': log['sha256']}
    folder = SCRATCH / ('compat-' + candidate + '-' + suffix + tail)
    receipt = copy(folder / 'compatibility.json',
                   'selected-proofs/compat-' + candidate + '-' + suffix + '.json')
    positive = copy(folder / 'compatibility-analysis.log',
                    'selected-proofs/compat-' + candidate + '-' + suffix + '-analysis.log')
    negative = copy(folder / 'negative-analysis.log',
                    'selected-proofs/compat-' + candidate + '-' + suffix + '-negative.log')
    value = json.loads((HERE / receipt['path']).read_text())
    if (value.get('passed') is not True or value.get('case_id') != case
            or value.get('candidate_id') != candidate
            or value.get('construction_sha256') != selected['construction_sha256']
            or value.get('log_sha256') != positive['sha256']
            or value.get('negative_log_sha256') != negative['sha256']):
        raise ValueError('Exact compatibility binding differs: ' + candidate + ' ' + suffix)
    selected['compatibility'] = {'receipt': receipt['path'], 'sha256': receipt['sha256'],
                                 'log': positive['path'], 'negative_log': negative['path'],
                                 'command': ('.venv-cpu/bin/python -B runtime.py compatibility --manifest work/' +
                                     AID + ('/selected-compatibility-manifest.json' if candidate == 'primary'
                                            else '/selected-fallback-draft.json') +
                                     ' --case ' + case + (' --candidate fallback1' if candidate == 'fallback1' else '') +
                                     ' --output .runtime-work/nrs213-resume-5/compat-' +
                                     candidate + '-' + suffix + tail + ' --library runtime/library --validator ' +
                                     '.runtime-work/nrs213-resume/current-decoder/.lake/build/bin/adapterCheck')}


def main():
    manifest = json.loads((HERE / 'selected-fallback-draft.json').read_text())
    primary_manifest = json.loads((HERE / 'selected-compatibility-manifest.json').read_text())
    manifest.update(format='worker-execution-manifest',
                    status='selected_delivery_prepared',
                    runtime_manifest_sha256=sha(REPO / 'runtime/SOURCE-MANIFEST.json'))
    for suffix, entry in zip(SUFFIXES, manifest['cases']):
        entry['fixture_recipe'] = next(item['fixture_recipe'] for item in primary_manifest['cases']
                                       if item['case_id'] == entry['case_id'])
        bind_proof(entry, 'primary', suffix)
        bind_proof(entry, 'fallback1', suffix)
        physical = HERE / 'physical-proof' / (suffix + '-receipt.json')
        receipt = json.loads(physical.read_text())
        if receipt['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Physical proof binds stale construction: ' + suffix)
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)),
                                         'sha256': sha(physical)}
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        entry['delivery_readiness'] = 'incomplete'
        entry['delivery_acceptance'] = {
            'case_id': entry['case_id'], 'sets': ['full-train'], 'checks': list(CHECKS),
            'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
            'negative_expected_error': 'Missing original source: exact original Native result',
            'command': '.venv-cpu/bin/python -B work/' + AID + '/delivery_audit.py --case ' +
                       entry['case_id'] + ' --self-test',
            'test_exit_code': 0, 'test_log': 'delivery-proofs/' + suffix + '-positive.log',
            'test_log_sha256': sha(HERE / 'delivery-proofs' / (suffix + '-positive.log')),
            'negative_command': '.venv-cpu/bin/python -B work/' + AID +
                                '/delivery_audit.py --case ' + entry['case_id'] +
                                ' --self-test --negative',
            'negative_exit_code': 1, 'negative_log': 'delivery-proofs/' + suffix + '-negative.log',
            'negative_log_sha256': sha(HERE / 'delivery-proofs' / (suffix + '-negative.log'))}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(part['content'] for part in construction['files']
                                 if part['path'] == 'config.json'))
        required = set(config['required_atoms']) | {
            channel['name'] for channel in construction['recording_description']['channels']}
        entry['acquisition'] = {name: {'entrypoint': 'runner.py',
            'method': 'same-tick original Native actor, road, sight ray and four-camera acquisition',
            'evidence': ('native-feature-source.jsonl, road-context.json, trace.jsonl, '
                         'video_frames.jsonl, capture/evidence.jsonl')}
            for name in sorted(required)}
        entry['post_capture'] = {'recorded_only': True,
            'command': '.venv-cpu/bin/python -B runtime.py process-saved --manifest work/' + AID +
                       '/execution-manifest.json --case ' + entry['case_id'] +
                       ' --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command': 'cat $OUTPUT/versions/*/feedback.json # ' + entry['case_id']}
    save(HERE / 'execution-manifest.json', manifest)
    print(json.dumps({'cases': len(manifest['cases']),
                      'execution_manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
