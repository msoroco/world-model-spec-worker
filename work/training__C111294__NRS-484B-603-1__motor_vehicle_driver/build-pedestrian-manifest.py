"""Bind source-shaped pedestrian CPU chains to exact selected case IDs."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(relative):
    return hashlib.sha256((HERE / relative).read_bytes()).hexdigest()


def proof(suffix, candidate):
    stem = suffix if candidate == 'primary' else suffix + '-fallback1'
    base = 'pedestrian-branch-drafts/' + stem + '/'
    construction = base + 'construction.json'
    return {'construction': construction,
            'construction_sha256': sha(construction),
            'offline': {'case_id': HERE.name + '__' + suffix,
                        'candidate_id': candidate,
                        'construction_sha256': sha(construction),
                        'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name + '/' + suffix + '-diagnostic-manifest.json --case ' + HERE.name + '__' + suffix + ' --candidate ' + candidate + ' --output .runtime-work/c111294-' + stem + '-offline-v2 --python "$PWD/.venv-cpu/bin/python"',
                        'exit_code': 0, 'log': base + 'offline.log',
                        'log_sha256': sha(base + 'offline.log')},
            'compatibility': {'receipt': base + 'compatibility.json',
                              'sha256': sha(base + 'compatibility.json'),
                              'log': base + 'analysis.log',
                              'negative_log': base + 'negative.log'}}


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    manifest['cases'] = [row for row in manifest['cases'] if '__pedestrian_probe_' not in row['case_id']]
    for suffix in ('pedestrian_probe_a', 'pedestrian_probe_b'):
        old = suffix.replace('pedestrian_', 'weather_')
        source = next(row for row in manifest['cases'] if row['case_id'].endswith('__' + old))
        entry = deepcopy(source)
        entry['case_id'] = HERE.name + '__' + suffix
        entry['measurement_contract'] = suffix + '-measurement-contract.json'
        entry['measurement_procedure']['output_schema'] = 'c111294-pedestrian-saved-diagnostic-v1'
        primary, fallback = proof(suffix, 'primary'), proof(suffix, 'fallback1')
        entry.update(primary)
        entry['negative'] = {'log': primary['compatibility']['negative_log']}
        entry['fixture_recipe'] = 'work/' + HERE.name + '/pedestrian-branch-drafts/' + suffix + '/recipe.json'
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Original Native walker crossing, ego speed and conflict distance can differ from synthetic diagnostics; retry changes the common other-vehicle spawn timing only.'}
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': fallback['construction'],
            'construction_sha256': fallback['construction_sha256'],
            'trigger': {'source': 'original Native ego speed, pedestrian pose and other-vehicle trajectory',
                        'metric': 'approach reduction and conflict timing with original walker readback',
                        'failure_condition': 'Primary speed profile or source-reviewed other-traffic timing fails physical target with pedestrian present'},
            'changed_knobs': ['common other-vehicle spawn position; same walker route and camera contract'],
            'offline': fallback['offline'], 'compatibility': fallback['compatibility'],
            'fixture_recipe': entry['fixture_recipe']}]
        physical = 'physical-proof/' + suffix + '/proof.json'
        entry['physical_preparation'] = {'receipt': physical, 'sha256': sha(physical)}
        del entry['acquisition']['weather_parameters']
        entry['acquisition']['pedestrian_pose'] = {
            'entrypoint': 'runner.py',
            'method': 'Original Native walker actor transform readback on 600 joined frames',
            'evidence': 'native_samples.jsonl, context.json and capture/evidence.jsonl'}
        entry['acquisition']['pedestrian_hazard'] = {
            'entrypoint': 'runner.py',
            'method': 'Original Native walker route and independent highway conflict review',
            'evidence': 'context.json and capture/evidence.jsonl'}
        post = entry['post_capture']
        post['command'] = post['command'].replace('__' + old, '__' + suffix)
        post['test_log'] = 'pedestrian-branch-drafts/' + suffix + '/saved.log'
        post['test_log_sha256'] = sha(post['test_log'])
        post['processing_receipt'] = 'pedestrian-branch-drafts/' + suffix + '/processing.json'
        post['processing_sha256'] = sha(post['processing_receipt'])
        acceptance = entry['delivery_acceptance']
        acceptance['case_id'] = entry['case_id']
        acceptance['command'] = acceptance['command'].replace('__' + old, '__' + suffix)
        acceptance['negative_command'] = acceptance['negative_command'].replace('__' + old, '__' + suffix)
        acceptance['test_log'] = 'delivery-' + suffix + '-positive.log'
        acceptance['test_log_sha256'] = sha(acceptance['test_log'])
        acceptance['negative_log'] = 'delivery-' + suffix + '-negative.log'
        acceptance['negative_log_sha256'] = sha(acceptance['negative_log'])
        manifest['cases'].append(entry)
    for row in manifest['cases']:
        row['delivery_acceptance']['script_sha256'] = sha('delivery_audit.py')
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    config_path = HERE / 'config.json'
    config = json.loads(config_path.read_text())
    config['supported_case_ids'] = [entry['case_id'] for entry in manifest['cases']]
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    print(sha('execution-manifest.json'))


if __name__ == '__main__':
    main()
