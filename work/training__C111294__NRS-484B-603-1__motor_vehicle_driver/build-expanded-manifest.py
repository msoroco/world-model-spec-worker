"""Bind four exact intersection and wet-weather CPU proof chains."""
import hashlib
import json
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256((HERE / path).read_bytes()).hexdigest()


def proof(suffix, candidate):
    stem = suffix if candidate == 'primary' else suffix + '-fallback1'
    base = 'weather-branch-drafts/' + stem + '/'
    return {'construction': base + 'construction.json',
            'construction_sha256': sha(base + 'construction.json'),
            'offline': {'case_id': HERE.name + '__' + suffix,
                        'candidate_id': candidate,
                        'construction_sha256': sha(base + 'construction.json'),
                        'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name + '/' + suffix + '-diagnostic-manifest.json --case ' + HERE.name + '__' + suffix + ' --candidate ' + candidate + ' --output .runtime-work/c111294-weather-offline-' + suffix + ('-fallback1' if candidate != 'primary' else '') + ' --python "$PWD/.venv-cpu/bin/python"',
                        'exit_code': 0, 'log': base + 'offline.log',
                        'log_sha256': sha(base + 'offline.log')},
            'compatibility': {'receipt': base + 'compatibility.json',
                              'sha256': sha(base + 'compatibility.json'),
                              'log': base + 'analysis.log',
                              'negative_log': base + 'negative.log'}}


def main():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    manifest['cases'] = [e for e in manifest['cases'] if not e['case_id'].endswith(('__weather_probe_a', '__weather_probe_b'))]
    for old, suffix in (('probe_a', 'weather_probe_a'), ('probe_b', 'weather_probe_b')):
        parent = next(e for e in manifest['cases'] if e['case_id'].endswith('__' + old))
        entry = deepcopy(parent)
        entry['case_id'] = HERE.name + '__' + suffix
        entry['id'] = 'primary'
        entry['measurement_contract'] = suffix + '-measurement-contract.json'
        entry['measurement_procedure']['output_schema'] = 'c111294-weather-saved-diagnostic-v1'
        primary, fallback = proof(suffix, 'primary'), proof(suffix, 'fallback1')
        entry.update(primary)
        entry['negative'] = {'log': primary['compatibility']['negative_log']}
        entry['fixture_recipe'] = 'work/' + HERE.name + '/weather-branch-drafts/' + suffix + '/recipe.json'
        entry['candidate_risk'] = {'status': 'physical', 'reason': 'Original Native wet-surface speed realization and cross-traffic timing may differ from synthetic diagnostics; the source-measured fallback changes only shared cross-traffic spawn.'}
        entry['candidates'] = [{'id': 'fallback1', 'construction': fallback['construction'],
                                'construction_sha256': fallback['construction_sha256'],
                                'trigger': {'source': 'original Native speed, weather readback and other-vehicle trajectory',
                                            'metric': 'approach reduction and cross-traffic timing under wet condition',
                                            'failure_condition': 'Primary speed profile or source-reviewed cross-traffic timing fails physical target under the wet condition'},
                                'changed_knobs': ['common other-vehicle spawn position; same wet-weather preset and camera contract'],
                                'offline': fallback['offline'], 'compatibility': fallback['compatibility'],
                                'fixture_recipe': entry['fixture_recipe']}]
        physical = 'physical-proof/' + suffix + '/proof.json'
        entry['physical_preparation'] = {'receipt': physical, 'sha256': sha(physical)}
        entry['acquisition']['weather_parameters'] = {'entrypoint': 'runner.py',
            'method': 'Original Native world.get_weather readback and 600 frame capture/evidence weather values',
            'evidence': 'context.json and capture/evidence.jsonl'}
        post = entry['post_capture']
        post['command'] = post['command'].replace('__' + old, '__' + suffix)
        post['test_log'] = 'weather-branch-drafts/' + suffix + '/saved.log'
        post['test_log_sha256'] = sha(post['test_log'])
        post['processing_receipt'] = 'weather-branch-drafts/' + suffix + '/processing.json'
        post['processing_sha256'] = sha(post['processing_receipt'])
        acceptance = entry['delivery_acceptance']
        acceptance['case_id'] = entry['case_id']
        acceptance['script_sha256'] = sha(acceptance['script'])
        acceptance['command'] = acceptance['command'].replace('__' + old, '__' + suffix)
        acceptance['negative_command'] = acceptance['negative_command'].replace('__' + old, '__' + suffix)
        acceptance['test_log'] = 'delivery-' + suffix + '-positive.log'
        acceptance['test_log_sha256'] = sha(acceptance['test_log'])
        acceptance['negative_log'] = 'delivery-' + suffix + '-negative.log'
        acceptance['negative_log_sha256'] = sha(acceptance['negative_log'])
        manifest['cases'].append(entry)
    for entry in manifest['cases']:
        entry['delivery_acceptance']['script_sha256'] = sha('delivery_audit.py')
    (HERE / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(sha('execution-manifest.json'))


if __name__ == '__main__':
    main()
