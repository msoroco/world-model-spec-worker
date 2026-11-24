"""Build twelve unselected exact 600-frame fallback CPU constructions."""
import copy
import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
CASES = ('witness_1', 'witness_2', 'exception_1_1', 'exception_1_2')
CANDIDATES = ('fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change(value):
    if isinstance(value, dict):
        return {key: change(item) for key, item in value.items()}
    if isinstance(value, list):
        return [change(item) for item in value]
    if isinstance(value, str):
        return re.sub(r'(?<![0-9])480(?![0-9])', '600',
                      re.sub(r'(?<![0-9])24(?![0-9])', '30', value))
    if type(value) in (int, float) and value in (24, 480):
        return 30 if value == 24 else 600
    return value


def config(construction):
    return json.loads(next(item['content'] for item in construction['files']
                           if item['path'] == 'config.json'))


def main():
    old = json.loads((HERE / 'execution-manifest.json').read_text())
    rows = []
    for case in CASES:
        manifest = json.loads((HERE / f'long-capture-matrix-{case}-manifest.json').read_text())
        entry = manifest['cases'][0]
        for stale in ('offline', 'compatibility', 'negative', 'physical_preparation',
                      'delivery_acceptance', 'post_capture'):
            entry.pop(stale, None)
        entry['kind'] = 'unselected_cpu_diagnostic'
        original_entry = next(item for item in old['cases'] if item['case_id'] == entry['case_id'])
        primary = json.loads((HERE / entry['construction']).read_text())
        primary_config = config(primary)
        for name in CANDIDATES:
            source_entry = next(item for item in original_entry['candidates'] if item['id'] == name)
            source = HERE / source_entry['construction']
            construction = change(json.loads(source.read_text()))
            assert construction['case_id'] == primary['case_id']
            assert construction['cell_id'] == primary['cell_id']
            assert construction['law_id'] == primary['law_id']
            assert construction['actor'] == primary['actor']
            candidate_config = config(construction)
            assert candidate_config['duration_s'] == 30 and candidate_config['rate_hz'] == 20
            assert candidate_config['knobs']['duration_s'] == 30
            assert len(candidate_config['cameras']) == 4
            changed = {key for key in primary_config['knobs']
                       if primary_config['knobs'][key] != candidate_config['knobs'][key]}
            assert changed == set(source_entry['changed_knobs']), (case, name, changed)
            assert candidate_config['candidate_id'] == name
            target = HERE / 'long-capture-fallbacks' / case / name / 'construction.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(construction, indent=2) + '\n')
            entry['candidates'].append({
                'id': name, 'construction': str(target.relative_to(HERE)),
                'construction_sha256': sha(target),
                'trigger': copy.deepcopy(source_entry['trigger']),
                'changed_knobs': list(source_entry['changed_knobs']),
            })
            rows.append({'case': case, 'candidate': name, 'construction_sha256': sha(target),
                         'changed_knob': next(iter(changed)), 'frames': 600})
        manifest['status'] = 'unselected_30_second_cpu_fallback_migration'
        path = HERE / f'long-capture-fallbacks-{case}-manifest.json'
        path.write_text(json.dumps(manifest, indent=2) + '\n')
    receipt = {'format': 'c111256-unselected-600-frame-fallback-constructions',
               'passed': True, 'selected': False, 'cases': len(CASES),
               'candidates': rows, 'physical_observation': False}
    target = HERE / 'long-capture-fallbacks' / 'build-receipt.json'
    target.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'candidates': len(rows), 'receipt_sha256': sha(target)}))


if __name__ == '__main__':
    main()
