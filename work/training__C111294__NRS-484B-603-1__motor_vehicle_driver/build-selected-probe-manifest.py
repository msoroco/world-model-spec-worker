"""Bind tested exact intersection probes without claiming full delivery readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return path.relative_to(HERE).as_posix()


def proof(suffix, candidate):
    key = suffix + ('' if candidate == 'primary' else '-' + candidate)
    path = HERE / f'current-v2-{key}-compatibility.json'
    result = json.loads(path.read_text())
    positive = HERE / f'current-v2-{key}-positive.log'
    negative = HERE / f'current-v2-{key}-negative.log'
    if (result['passed'] is not True or result['candidate_id'] != candidate or
            result['log_sha256'] != sha(positive) or
            result['negative_log_sha256'] != sha(negative) or
            result['negative_error_contains'] not in negative.read_text()):
        raise ValueError('Stale public diagnostic: ' + key)
    return {'receipt': rel(path), 'sha256': sha(path), 'log': rel(positive),
            'negative_log': rel(negative)}


def offline(suffix, candidate, manifest):
    construction = HERE / (f'current-v2-{suffix}-diagnostic/construction.json'
                           if candidate == 'primary' else
                           f'current-v2-{suffix}-{candidate}-diagnostic/construction.json')
    log = HERE / f'current-v2-{suffix}-{candidate}-offline.log'
    if '"passed": true' not in log.read_text() or not log.read_text().rstrip().endswith('OK'):
        raise ValueError('Offline CPU check changed: ' + suffix + '/' + candidate)
    return {'case_id': HERE.name + '__' + suffix, 'candidate_id': candidate,
            'construction_sha256': sha(construction),
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/{rel(manifest)} --case {HERE.name}__{suffix} --candidate {candidate} --output .runtime-work/c111294-current/offline-{suffix}-{candidate}-fixed --python "$PWD/.venv-cpu/bin/python"',
            'exit_code': 0, 'log': rel(log), 'log_sha256': sha(log)}


def main():
    entries = []
    for suffix in ('probe_a', 'probe_b'):
        source_manifest = HERE / f'current-v2-{suffix}-diagnostic-manifest.json'
        source = json.loads(source_manifest.read_text())['cases'][0]
        construction = HERE / source['construction']
        if sha(construction) != source['construction_sha256']:
            raise ValueError('Primary construction changed: ' + suffix)
        fallback_manifest = HERE / f'current-v2-{suffix}-fallback1-diagnostic-manifest.json'
        fallback = json.loads(fallback_manifest.read_text())['cases'][0]['candidates'][0]
        fallback_path = HERE / fallback['construction']
        if sha(fallback_path) != fallback['construction_sha256']:
            raise ValueError('Fallback construction changed: ' + suffix)
        source['kind'] = 'delivery'
        source['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Original Native cross-traffic timing and ego approach-speed realization are unobserved; a source-measured retry may shift common cross-traffic spawn or earlier braking without changing case or camera contract.'}
        source['offline'] = offline(suffix, 'primary', source_manifest)
        source['compatibility'] = proof(suffix, 'primary')
        source['negative'] = {'log': source['compatibility']['negative_log']}
        source['physical_preparation'] = {
            'receipt': f'physical-proof/{suffix}/proof.json',
            'sha256': sha(HERE / f'physical-proof/{suffix}/proof.json')}
        source['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                    'host_env_var': 'CARLA_HOST',
                                    'port_env_var': 'CARLA_PORT'}
        trigger = ({'source': 'original Native ego velocity and intersection approach position',
                    'metric': 'approach-to-preentry speed reduction, mph',
                    'failure_condition': 'primary reduction below 3 mph engineering retry trigger'}
                   if suffix == 'probe_a' else
                   {'source': 'original Native ego velocity and other-vehicle trajectory',
                    'metric': 'approach-to-preentry reduction and original other-vehicle timing',
                    'failure_condition': 'primary reduction above 1 mph or original other-vehicle timing fails source review'})
        source['candidates'] = [{**fallback,
            'trigger': trigger,
            'changed_knobs': (['earlier brake onset', 'common other-vehicle spawn position']
                              if suffix == 'probe_a' else
                              ['common other-vehicle spawn position; speed held equal across pair']),
            'offline': offline(suffix, 'fallback1', fallback_manifest),
            'compatibility': proof(suffix, 'fallback1'),
            'fixture_recipe': source['fixture_recipe']}]
        config = json.loads(next(item['content'] for item in json.loads(construction.read_text())['files']
                                 if item['path'] == 'config.json'))
        acquired = set(config['required_atoms']) | {
            c['name'] for c in json.loads(construction.read_text())['recording_description']['channels']}
        source['acquisition'] = {name: {
            'entrypoint': 'runner.py',
            'method': '20 Hz original Native actor pose/velocity, road and camera acquisition with source-joined saved channels',
            'evidence': 'native_samples.jsonl, trace.jsonl, capture/evidence.jsonl, road.xodr and four synchronized original videos'}
            for name in sorted(acquired)}
        saved = HERE / f'current-v2-{suffix}-saved-processing.json'
        processing = json.loads(saved.read_text())
        if not (processing['passed'] and processing['recorded_only'] and
                processing['timestamp_joins']['frames'] == 600 and
                processing['physical_acceptance_claimed'] is False):
            raise ValueError('Recorded-only processing differs: ' + suffix)
        log = HERE / f'current-v2-{suffix}-saved-process.log'
        source['post_capture'] = {
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {HERE.name}__{suffix} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command': 'cat $OUTPUT/v*/feedback.json',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': rel(log), 'test_log_sha256': sha(log),
            'processing_receipt': rel(saved), 'processing_sha256': sha(saved)}
        entries.append(source)
    selected = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'status': 'selected_cpu_preparation_diagnostic_only', 'cases': entries}
    path = HERE / 'selected-probe-manifest.json'
    path.write_text(json.dumps(selected, indent=2) + '\n')
    print(json.dumps({'selected_case_count': len(entries), 'sha256': sha(path)}))


if __name__ == '__main__':
    main()
