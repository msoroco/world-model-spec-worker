"""Bind passing current-runtime candidate receipts into exact delivery intent."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PUBLIC = HERE / 'current-public'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / 'current-execution-manifest.json').read_text())
    compat = json.loads((PUBLIC / 'candidate-compat-summary.json').read_text())
    saved = json.loads((PUBLIC / 'candidate-saved-summary.json').read_text())
    compat_by = {(x['case'], x['candidate']): x for x in compat['results']}
    saved_by = {(x['case'], x['candidate']): x for x in saved['results']}
    physical_index = json.loads((HERE / 'physical-proof/index.json').read_text())
    physical_by = {x['case_id']: x for x in physical_index['cases']}
    for case in manifest['cases']:
        suffix = case['case_id'].split('__')[-1]
        case['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                  'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        case['physical_preparation'] = physical_by[case['case_id']]
        construction = json.loads((HERE / case['construction']).read_text())
        config = next(json.loads(f['content']) for f in construction['files']
                      if f['path'] == 'config.json')
        names = set(config['required_atoms']) | {
            c['name'] for c in construction['recording_description']['channels']}
        case['acquisition'] = {
            name: {'entrypoint': 'runner.py',
                   'evidence': 'native_samples.jsonl, road_geometry.json, trace.jsonl, capture/evidence.jsonl',
                   'method': 'original 20 Hz Native map/body/frame joins; diagnostic source is synthetic'}
            for name in sorted(names)}
        for item in [case] + case['candidates']:
            candidate = item['id']
            cproof = compat_by[(suffix, candidate)]
            sproof = saved_by[(suffix, candidate)]
            if cproof['exit_code'] or sproof['offline']['exit_code'] or sproof['saved']['exit_code']:
                raise ValueError('Candidate proof failed: ' + suffix + '/' + candidate)
            if cproof['construction_sha256'] != item['construction_sha256']:
                raise ValueError('Construction changed: ' + suffix + '/' + candidate)
            log = sproof['offline']['log']
            item['offline'] = {'command': f'.venv-cpu/bin/python runtime.py offline --manifest {HERE.relative_to(ROOT) / "current-execution-manifest.json"} --case {case["case_id"]} --candidate {candidate} --output .runtime-work/c405647-current-{suffix}-{candidate}-offline --python .venv-cpu/bin/python',
                               'exit_code': 0, 'construction_sha256': item['construction_sha256'],
                               'log': log, 'log_sha256': sha(HERE / log)}
            files = cproof['files']
            item['compatibility'] = {'receipt': files['compatibility.json']['path'],
                                     'sha256': files['compatibility.json']['sha256'],
                                     'log': files['analysis.log']['path'],
                                     'negative_log': files['negative.log']['path']}
            item['negative'] = {'log': files['negative.log']['path']}
            item['saved_processing'] = {'receipt': sproof['saved']['receipt'],
                                        'sha256': sproof['saved']['receipt_sha256']}
        primary = case
        case['post_capture'] = {
            'recorded_only': True,
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case["case_id"]} --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0,
            'test_log': primary['saved_processing']['receipt'],
            'test_log_sha256': primary['saved_processing']['sha256']}
    manifest['status'] = 'delivery_prepared'
    manifest['delivery_ready'] = False
    manifest['original_native_observed'] = False
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': len(manifest['cases']),
                      'candidates': sum(1 + len(c['candidates']) for c in manifest['cases']),
                      'manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
