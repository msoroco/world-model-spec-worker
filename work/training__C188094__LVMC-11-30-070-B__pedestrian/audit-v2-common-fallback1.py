"""Independently audit the shared fallback policy and its three saved attempts."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def audit(attempts, saved):
    primary_manifest = read(HERE / 'v2-common-intersection-manifest.json')
    fallback_manifest = read(HERE / 'v2-common-fallback1-manifest.json')
    if len(primary_manifest['cases']) != 3 or len(fallback_manifest['cases']) != 3:
        raise ValueError('Three linked cases required')
    results = []
    roads = []
    for number, (original, entry) in enumerate(zip(primary_manifest['cases'], fallback_manifest['cases']), 1):
        if original['case_id'] != entry['case_id'] or original['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Fallback changed primary case binding')
        if len(entry['candidates']) != 1 or entry['candidates'][0]['id'] != 'fallback1':
            raise ValueError('Linked fallback missing')
        candidate = entry['candidates'][0]
        source = HERE / candidate['construction']
        if sha(source) != candidate['construction_sha256']:
            raise ValueError('Fallback construction hash changed')
        primary = read(HERE / original['construction'])
        alternative = read(source)
        files1 = {item['path']: item['content'] for item in primary['files']}
        files2 = {item['path']: item['content'] for item in alternative['files']}
        if files1.keys() != files2.keys():
            raise ValueError('Fallback implementation inventory changed')
        for name, content in files1.items():
            if name == 'runner.py':
                expected = content.replace('max(-0.2, min(0.2, x_error))',
                                           'max(-0.4, min(0.4, x_error))')
                if expected == content:
                    raise ValueError('Missing primary lateral correction site')
            elif name == 'config.json':
                config = json.loads(content)
                config['candidate_id'] = 'fallback1'
                expected = json.dumps(config, indent=2) + '\n'
            else:
                expected = content
            if files2[name] != expected:
                raise ValueError('Undeclared fallback source change: ' + name)
        prefix = f'v2-common-fallback1-probe{number}'
        compatibility_path = HERE / f'{prefix}-compatibility.json'
        negative_path = HERE / f'{prefix}-negative-analysis.log'
        processing_path = HERE / f'{prefix}-processing.json'
        compatibility = read(compatibility_path)
        processing = read(processing_path)
        if (compatibility['passed'] is not True or compatibility['candidate_id'] != 'fallback1'
                or compatibility['construction_sha256'] != candidate['construction_sha256']
                or compatibility['negative_log_sha256'] != sha(negative_path)):
            raise ValueError('Public positive or source-negative proof changed')
        if (processing['passed'] is not True or processing['recorded_only'] is not True
                or processing['originals_preserved'] is not True
                or processing['analysis_revision']['construction_sha256'] != candidate['construction_sha256']
                or processing['timestamp_joins']['frames'] != 600):
            raise ValueError('Recorded-only selected construction proof changed')
        attempt = attempts[number]
        saved_dir = saved[number]
        recipe_name = f'v2-common{number}-fixture-recipe.json' if number < 3 else 'v2-probe3-fixture-recipe.json'
        for item in read(HERE / recipe_name)['sources']:
            if sha(attempt / item['path']) != item['sha256']:
                raise ValueError('Original source changed: ' + item['path'])
        if sha(saved_dir / 'processing.json') != sha(processing_path):
            raise ValueError('Saved processing receipt differs')
        roads.append(sha(attempt / 'road.xodr'))
        result = read(saved_dir / 'analysis/result.json')
        if result['accepted'] is not False or result['legal_verdict_claimed'] is not False:
            raise ValueError('Diagnostic fixture claims acceptance')
        results.append({'case_id': entry['case_id'],
                        'construction_sha256': candidate['construction_sha256'],
                        'compatibility_sha256': sha(compatibility_path),
                        'negative_log_sha256': sha(negative_path),
                        'processing_sha256': sha(processing_path)})
    if len(set(roads)) != 1:
        raise ValueError('Fallback cases used different road geometry')
    return {'format': 'c188094-common-fallback1-cpu-audit', 'passed': True,
            'primary_manifest_sha256': sha(HERE / 'v2-common-intersection-manifest.json'),
            'fallback_manifest_sha256': sha(HERE / 'v2-common-fallback1-manifest.json'),
            'shared_road_xodr_sha256': roads[0], 'declared_only_change_verified': True,
            'cases': results, 'original_native_physical_observed': False,
            'business_district_confirmed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for number in (1, 2, 3):
        parser.add_argument(f'--attempt{number}', required=True, type=Path)
        parser.add_argument(f'--saved{number}', required=True, type=Path)
    args = parser.parse_args()
    result = audit({n: getattr(args, f'attempt{n}') for n in (1, 2, 3)},
                   {n: getattr(args, f'saved{n}') for n in (1, 2, 3)})
    (HERE / 'v2-common-fallback1-independent-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))
