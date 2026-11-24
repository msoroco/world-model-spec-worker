"""Audit exact fallback difference, public checks and saved-only selection."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit():
    selected = read(HERE / 'v2-selected-pair-manifest.json')
    manifest = read(HERE / 'v2-fallback1-manifest.json')
    results = []
    for number, (primary_entry, entry) in enumerate(zip(selected['cases'], manifest['cases']), 1):
        if entry['case_id'] != primary_entry['case_id'] or len(entry['candidates']) != 1:
            raise ValueError('Linked candidate/case identity changed')
        candidate = entry['candidates'][0]
        if candidate['id'] != 'fallback1':
            raise ValueError('Fallback candidate identity changed')
        primary = read(HERE / primary_entry['construction'])
        alternative = read(HERE / candidate['construction'])
        if sha(HERE / candidate['construction']) != candidate['construction_sha256']:
            raise ValueError('Fallback construction hash differs')
        files1 = {f['path']: f['content'] for f in primary['files']}
        files2 = {f['path']: f['content'] for f in alternative['files']}
        if files1.keys() != files2.keys():
            raise ValueError('Fallback source set differs')
        for name in files1:
            if name == 'runner.py':
                expected = files1[name].replace('max(-0.2, min(0.2, x_error))',
                                                'max(-0.4, min(0.4, x_error))')
            elif name == 'config.json':
                config = json.loads(files1[name])
                config['candidate_id'] = 'fallback1'
                expected = json.dumps(config, indent=2) + '\n'
            else:
                expected = files1[name]
            if files2[name] != expected:
                raise ValueError(f'Undeclared fallback change: {name}')
        prefix = f'v2-fallback1-probe{number}'
        compatibility = read(HERE / f'{prefix}-compatibility.json')
        processing = read(HERE / f'{prefix}-processing.json')
        negative = HERE / f'{prefix}-negative-analysis.log'
        if compatibility['passed'] is not True or compatibility['candidate_id'] != 'fallback1' or compatibility['construction_sha256'] != candidate['construction_sha256']:
            raise ValueError('Fallback public positive check differs')
        if compatibility['negative_log_sha256'] != sha(negative):
            raise ValueError('Fallback source-negative check differs')
        if processing['passed'] is not True or processing['recorded_only'] is not True or processing['originals_preserved'] is not True:
            raise ValueError('Fallback saved processing differs')
        if processing['analysis_revision']['construction_sha256'] != candidate['construction_sha256']:
            raise ValueError('Fallback saved selected construction differs')
        if processing['timestamp_joins']['frames'] != 600:
            raise ValueError('Fallback source joins incomplete')
        results.append({'case_id': entry['case_id'], 'construction_sha256': candidate['construction_sha256'],
                        'compatibility_sha256': sha(HERE / f'{prefix}-compatibility.json'),
                        'negative_log_sha256': sha(negative),
                        'processing_sha256': sha(HERE / f'{prefix}-processing.json')})
    return {'format': 'c188094-fallback1-cpu-audit', 'passed': True,
            'manifest_sha256': sha(HERE / 'v2-fallback1-manifest.json'),
            'declared_only_change_verified': True, 'cases': results,
            'original_native_physical_observed': False,
            'business_district_confirmed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    result = audit()
    (HERE / 'v2-fallback1-independent-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
