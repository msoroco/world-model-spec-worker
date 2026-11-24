"""Compare exact source pairs while refusing synthetic legal promotion."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def audit(comparison, left, right, diagnostic):
    plan = read(HERE / 'case-plan.json')
    spec = next((x for x in plan['comparisons'] if x['comparison_id'] == comparison), None)
    if spec is None or len(spec['case_ids']) != 2:
        raise ValueError('Unselected comparison')
    manifest = read(HERE / 'execution-manifest.json')
    sources = []
    for path, case in zip((left, right), spec['case_ids']):
        selection = read(path / 'candidate-selection.json')
        entry = next(x for x in manifest['cases'] if x['case_id'] == case)
        if selection['case_id'] != case or selection['candidate_id'] != 'primary' or selection['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Comparison source selection differs')
        samples = rows(path / 'native_samples.jsonl')
        if len(samples) != 600:
            raise ValueError('Comparison source lacks 600 Native samples')
        sources.append({'path': path, 'samples': samples, 'geometry_sha256': sha(path / 'road_geometry.json'),
                        'selection_sha256': sha(path / 'candidate-selection.json'),
                        'source_kind': read(path / 'capture/manifest.json').get('source_kind')})
    if sources[0]['geometry_sha256'] != sources[1]['geometry_sha256']:
        raise ValueError('Comparison road geometry differs')
    a, b = (x['samples'] for x in sources)
    suffix = comparison.rsplit('__', 1)[1]
    if suffix == 'witness_comparison':
        difference = sum(x['native_center_xy_m'] != y['native_center_xy_m'] for x, y in zip(a, b))
        if difference == 0 or any(x['white_cane_declared'] or y['white_cane_declared'] for x, y in zip(a, b)):
            raise ValueError('Witness behavior comparison variable absent')
        named_difference = {'ego_trajectory_changed_frames': difference}
    elif suffix == 'exception_1_comparison':
        if any(x['native_center_xy_m'] != y['native_center_xy_m'] for x, y in zip(a, b)):
            raise ValueError('Exception comparison changed ego trajectory')
        if not all(x['white_cane_declared'] is False and y['white_cane_declared'] is True for x, y in zip(a, b)):
            raise ValueError('Exception declaration difference absent')
        named_difference = {'synthetic_white_cane_declaration_changed_frames': 600}
    else:
        raise ValueError('Unsupported comparison')
    if diagnostic:
        return {'format': 'c111256-comparison-audit', 'comparison_id': comparison,
                'diagnostic_only': True, 'accepted': False, 'source_cases': spec['case_ids'],
                'fixed_road_geometry_sha256': sources[0]['geometry_sha256'],
                'named_difference': named_difference,
                'original_native_verified': False, 'legal_verdict_claimed': False}
    if any(x['source_kind'] != 'original_native' for x in sources):
        raise ValueError('Original Native comparison sources required')
    if not all((x['path'] / 'independent-physical-review.json').is_file() for x in sources):
        raise ValueError('Independent physical comparison review required')
    raise ValueError('Manual comparison audit required before legal promotion')


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--comparison', required=True)
    p.add_argument('--left', type=Path, required=True)
    p.add_argument('--right', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--diagnostic', action='store_true')
    a = p.parse_args()
    result = audit(a.comparison, a.left, a.right, a.diagnostic)
    if a.output.exists():
        raise ValueError('Retain previous comparison audit')
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison': a.comparison, 'diagnostic_only': a.diagnostic}))
