"""Rebind preserved selected delivery cases after complete current-runtime CPU reproof."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PREFIX = f'work/{HERE.name}/'


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def compatibility(suffix, candidate, runtime_hash, construction_hash):
    stem = f'current-runtime-{suffix}-{candidate}'
    path = HERE/(stem+'-compatibility.json')
    analysis = HERE/(stem+'-analysis.log')
    negative = HERE/(stem+'-negative.log')
    data = read(path)
    require(data['passed'] and data['runtime_manifest_sha256'] == runtime_hash and
            data['construction_sha256'] == construction_hash and
            'Missing required source: native_samples.jsonl' in negative.read_text(),
            'Unproven current-runtime compatibility: '+stem)
    return {'receipt': path.name, 'sha256': sha(path), 'log': analysis.name,
            'negative_log': negative.name}


def offline(entry, suffix, candidate, construction_hash):
    log = HERE/f'current-runtime-reproof-{suffix}-{candidate}-offline.log'
    data = read(log)
    require(data['offline_passed'] and data['candidate_id'] == candidate and
            data['case_id'] == entry['case_id'], 'Offline proof missing: '+suffix+' '+candidate)
    return {'exit_code': 0, 'construction_sha256': construction_hash,
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest {PREFIX}current-runtime-reproof-manifest.json '
                       f'--case {entry["case_id"]} --candidate {candidate} '
                       f'--output .runtime-work/c110812-current-runtime-reproof-{suffix}-{candidate}',
            'log': log.name, 'log_sha256': sha(log)}


def main():
    current = sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json')
    harness = read(HERE/'current-runtime-reproof-manifest.json')
    progress = read(HERE/'current-runtime-matrix-progress.json')
    require(harness['runtime_manifest_sha256'] == current and progress['runtime_manifest_sha256'] == current,
            'Current runtime binding differs')
    require(progress['completed'] == 12 and progress['required'] == 12 and len(progress['rows']) == 12,
            'All twelve current-runtime compatibility/saved chains are required')
    old = read(HERE/'execution-manifest.json')
    by_case = {e['case_id']: e for e in harness['cases']}
    require(set(by_case) == {e['case_id'] for e in old['cases']}, 'Selected case set changed')
    for entry in old['cases']:
        new = by_case[entry['case_id']]
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        require(entry['construction_sha256'] == new['construction_sha256'], 'Primary construction changed')
        require({c['id']: c['construction_sha256'] for c in entry['candidates']} ==
                {c['id']: c['construction_sha256'] for c in new['candidates']}, 'Fallback construction changed')
        entry['offline'] = offline(entry, suffix, 'primary', entry['construction_sha256'])
        entry['compatibility'] = compatibility(suffix, 'primary', current, entry['construction_sha256'])
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        for candidate in entry['candidates']:
            name = candidate['id']
            candidate['offline'] = offline(entry, suffix, name, candidate['construction_sha256'])
            candidate['compatibility'] = compatibility(suffix, name, current, candidate['construction_sha256'])
        saved = HERE/f'current-runtime-{suffix}-primary-saved-receipt.json'
        saved_data = read(saved)['result']
        require(saved_data['passed'] and saved_data['recorded_only'] and
                saved_data['analysis_revision']['runtime_manifest_sha256'] == current and
                saved_data['analysis_revision']['construction_sha256'] == entry['construction_sha256'],
                'Primary saved proof differs: '+suffix)
        post = entry['post_capture']
        post['test_log'] = saved.name
        post['test_log_sha256'] = sha(saved)
        post['test_exit_code'] = 0
        physical = HERE/'current-runtime-physical-fixtures'/suffix/'proof.json'
        entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)), 'sha256': sha(physical)}
        acceptance = entry['delivery_acceptance']
        acceptance['script_sha256'] = sha(HERE/acceptance['script'])
        for key, name in (('test_log', f'current-runtime-delivery-{suffix}-positive.log'),
                          ('negative_log', f'current-runtime-delivery-{suffix}-negative.log')):
            path = HERE/name
            require(path.is_file(), 'Delivery audit missing: '+name)
            acceptance[key] = name
            acceptance[key+'_sha256'] = sha(path)
        require('"passed": true' in (HERE/acceptance['test_log']).read_text() and
                acceptance['negative_expected_error'] in (HERE/acceptance['negative_log']).read_text(),
                'Delivery audit positive/negative incomplete: '+suffix)
        comparison = entry['comparison_audit']
        comparison['script_sha256'] = sha(HERE/comparison['script'])
        pair = 'control' if suffix == 'control' else 'straight-corner'
        for key, name in (('test_log', f'current-runtime-comparison-{pair}-positive.log'),
                          ('negative_log', f'current-runtime-comparison-{pair}-negative-drift.log')):
            path = HERE/name
            require(path.is_file(), 'Comparison audit missing: '+name)
            comparison[key] = name
            comparison[key+'_sha256'] = sha(path)
        require('"passed": true' in (HERE/comparison['test_log']).read_text() and
                comparison['negative_expected_error'] in (HERE/comparison['negative_log']).read_text(),
                'Comparison positive/negative incomplete: '+pair)
        trigger = HERE/'current-runtime-trigger-audit.log'
        require(trigger.is_file() and '"passed": true' in trigger.read_text(),
                'Current fallback trigger audit missing')
        entry['candidate_trigger_test'] = {
            'command': f'.venv-cpu/bin/python {PREFIX}audit-fallback3.py',
            'test_log': trigger.name, 'test_log_sha256': sha(trigger), 'test_exit_code': 0}
    old['runtime_manifest_sha256'] = current
    old['status'] = 'selected_cpu_partial'
    path = HERE/'execution-manifest.json'
    path.write_text(json.dumps(old, indent=2)+'\n')
    print(json.dumps({'cases': len(old['cases']), 'manifest_sha256': sha(path),
                      'runtime_manifest_sha256': current}))


if __name__ == '__main__':
    main()
