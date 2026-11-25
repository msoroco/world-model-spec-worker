"""Bind hill crest CPU proofs to exact selected case entries."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def digest(relative):
    return hashlib.sha256((HERE / relative).read_bytes()).hexdigest()


def update_proof(item, suffix, candidate):
    stem = suffix if candidate == 'primary' else suffix + '-fallback1'
    base = 'crest-branch-drafts/' + stem + '/'
    construction = base + 'construction.json'
    receipt = base + 'compatibility.json'
    payload = json.loads((HERE / receipt).read_text())
    if (payload.get('passed') is not True or
            payload.get('case_id') != HERE.name + '__' + suffix or
            payload.get('candidate_id') != candidate or
            payload.get('construction_sha256') != digest(construction) or
            payload.get('log_sha256') != digest(base + 'analysis.log') or
            payload.get('negative_log_sha256') != digest(base + 'negative.log')):
        raise ValueError('Stale hill crest proof: ' + stem)
    item.update(construction=construction, construction_sha256=digest(construction),
                offline={'case_id': HERE.name + '__' + suffix,
                         'candidate_id': candidate,
                         'construction_sha256': digest(construction),
                         'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name + '/' + suffix + '-diagnostic-manifest.json --case ' + HERE.name + '__' + suffix + ' --candidate ' + candidate + ' --output .runtime-work/c111294-' + stem + '-offline-v1 --python "$PWD/.venv-cpu/bin/python"',
                         'exit_code': 0, 'log': base + 'offline.log',
                         'log_sha256': digest(base + 'offline.log')},
                compatibility={'receipt': receipt, 'sha256': digest(receipt),
                               'log': base + 'analysis.log',
                               'negative_log': base + 'negative.log'})


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    manifest['cases'] = [row for row in manifest['cases'] if '__crest_probe_' not in row['case_id']]
    for letter in 'ab':
        suffix = 'crest_probe_' + letter
        source = next(row for row in manifest['cases'] if row['case_id'].endswith('__obstruction_probe_' + letter))
        entry = copy.deepcopy(source)
        entry['case_id'] = HERE.name + '__' + suffix
        entry['measurement_contract'] = suffix + '-measurement-contract.json'
        entry['measurement_procedure']['output_schema'] = 'c111294-crest-saved-diagnostic-v1'
        entry['fixture_recipe'] = 'work/' + HERE.name + '/crest-branch-drafts/' + suffix + '/recipe.json'
        entry['candidate_risk'] = {'status': 'physical', 'reason': 'Original Native crest route and realized speed can differ from synthetic diagnostics; retry adjusts only common other-vehicle timing.'}
        update_proof(entry, suffix, 'primary')
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        fallback = entry['candidates'][0]
        update_proof(fallback, suffix, 'fallback1')
        fallback['trigger'] = {'source': 'original Native ego height and speed with source road elevation',
                               'metric': 'crest rise/fall and approach speed reduction',
                               'failure_condition': 'Primary crest route or speed realization fails physical target'}
        fallback['changed_knobs'] = ['common other-vehicle spawn position; same crest road and camera contract']
        fallback['fixture_recipe'] = entry['fixture_recipe']
        receipt = 'physical-proof/' + suffix + '/proof.json'
        entry['physical_preparation'] = {'receipt': receipt, 'sha256': digest(receipt)}
        for key in ('obstruction_pose', 'highway_obstruction'):
            entry['acquisition'].pop(key, None)
        entry['acquisition']['crest_design'] = {'entrypoint': 'runner.py',
                                                  'method': 'Original Native road elevation and 600-frame ego height readback',
                                                  'evidence': 'road.xodr, context.json, native_samples.jsonl and capture/evidence.jsonl'}
        post = entry['post_capture']
        post['command'] = post['command'].replace('__obstruction_probe_' + letter, '__' + suffix)
        post['test_log'] = 'crest-branch-drafts/' + suffix + '/saved.log'
        post['test_log_sha256'] = digest(post['test_log'])
        post['processing_receipt'] = 'crest-branch-drafts/' + suffix + '/processing.json'
        post['processing_sha256'] = digest(post['processing_receipt'])
        acceptance = entry['delivery_acceptance']
        acceptance['case_id'] = entry['case_id']
        acceptance['command'] = acceptance['command'].replace('__obstruction_probe_' + letter, '__' + suffix)
        acceptance['negative_command'] = acceptance['negative_command'].replace('__obstruction_probe_' + letter, '__' + suffix)
        acceptance['test_log'] = 'delivery-' + suffix + '-positive.log'
        acceptance['test_log_sha256'] = digest(acceptance['test_log'])
        acceptance['negative_log'] = 'delivery-' + suffix + '-negative.log'
        acceptance['negative_log_sha256'] = digest(acceptance['negative_log'])
        manifest['cases'].append(entry)
    for row in manifest['cases']:
        row['delivery_acceptance']['script_sha256'] = digest('delivery_audit.py')
        row['physical_preparation']['sha256'] = digest(row['physical_preparation']['receipt'])
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    config_path = HERE / 'config.json'
    config = json.loads(config_path.read_text())
    config['supported_case_ids'] = [entry['case_id'] for entry in manifest['cases']]
    config_path.write_text(json.dumps(config, indent=2) + '\n')
    construction_path = HERE / 'construction.json'
    construction = json.loads(construction_path.read_text())
    for file in construction['files']:
        if file['path'] == 'config.json':
            file['content'] = config_path.read_text()
    construction_path.write_text(json.dumps(construction, indent=2) + '\n')
    print(digest('execution-manifest.json'))


if __name__ == '__main__':
    main()
