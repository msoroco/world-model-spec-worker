"""Independently check active-pin source contrasts across all five A11 comparisons."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'
EXPECTED = {'witness_comparison': ('witness_1', 'witness_2'), 'numeric_1_comparison': ('numeric_1_0', 'numeric_1_1', 'numeric_1_2'), 'exception_1_comparison': ('exception_1_1', 'exception_1_2'), 'exception_2_comparison': ('exception_2_1', 'exception_2_2'), 'exception_3_comparison': ('exception_3_1', 'exception_3_2')}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def read(path):
    return json.loads(path.read_text())

def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]

def audit(corrupt_source=None):
    manifest = read(HERE / 'execution-manifest.json')
    plan = read(HERE / 'case-plan.json')
    current = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    if manifest['runtime_manifest_sha256'] != current:
        raise ValueError('Selected runtime pin changed')
    indexed = {entry['case_id'].rsplit('__', 1)[-1]: entry for entry in manifest['cases']}
    if set(indexed) != {suffix for group in EXPECTED.values() for suffix in group}:
        raise ValueError('Selected case set changed')
    found = {item['comparison_id'].rsplit('__', 1)[-1]: tuple(case.rsplit('__', 1)[-1] for case in item['case_ids']) for item in plan['comparisons']}
    if found != EXPECTED:
        raise ValueError('Planned comparison membership changed')
    cases = {}
    for suffix, entry in indexed.items():
        attempt = SCRATCH / 'c110454-active-saved' / suffix / 'attempt'
        saved = read(SCRATCH / 'c110454-active-saved' / suffix / 'processed/v0001/processing.json')
        public = read(SCRATCH / 'c110454-active-compat' / suffix / 'primary/compatibility.json')
        construction = read(HERE / entry['construction'])
        config = json.loads(next(item['content'] for item in construction['files'] if item['path'] == 'config.json'))
        if sha(HERE / entry['construction']) != entry['construction_sha256'] or public['construction_sha256'] != entry['construction_sha256'] or saved['native_revision']['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Construction binding differs: ' + suffix)
        if public['runtime_manifest_sha256'] != current or saved['analysis_revision']['runtime_manifest_sha256'] != current or not public['passed'] or not saved['passed']:
            raise ValueError('Active runtime receipt missing: ' + suffix)
        source_files = ('native_samples.jsonl', 'video_frames.jsonl', 'body_history.jsonl', 'native_parking_history.json', 'road_geometry.json')
        hashes = {}
        for name in source_files:
            source = corrupt_source if (suffix == 'numeric_1_1' and name == 'native_parking_history.json' and corrupt_source is not None) else attempt / name
            if not source.is_file():
                raise ValueError('Original comparison source absent: ' + suffix + '/' + name)
            hashes[name] = sha(source)
            if saved['original_source_hashes'].get(name) != hashes[name]:
                raise ValueError('Saved original comparison source changed: ' + suffix + '/' + name)
        samples = rows(attempt / 'native_samples.jsonl')
        frames = rows(attempt / 'video_frames.jsonl')
        bodies = rows(attempt / 'body_history.jsonl')
        if len(samples) != 600 or len(frames) != 600 or len(bodies) != 600 or any(a['native_frame'] != b['carla_frame'] or a['native_frame'] != c['frame'] or abs(a['time_s'] - b['time_s']) > 1e-8 or abs(a['time_s'] - c['time_s']) > 1e-8 or len(c['body_vertices_m']) != 8 for a, b, c in zip(samples, frames, bodies)):
            raise ValueError('Full-body source frame join changed: ' + suffix)
        if (config['law_id'], config['cell_id'], config['actor'], config['duration_s'], config['rate_hz']) != ('LVMC-11-52-130-A11', 'C110454', 'motor_vehicle_driver', 30, 20):
            raise ValueError('Frozen identity or recording window changed: ' + suffix)
        cameras = [(x['name'], x['width'], x['height']) for x in config['cameras']]
        if cameras != [('overview', 1920, 1080), ('approach', 1280, 720), ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]:
            raise ValueError('Four camera comparison profile changed: ' + suffix)
        values = public['measurement_examples']
        measurement = values.get('parked_body_distance_and_rest_interval', {}).get('value')
        exception = values.get('exception_source_context', {}).get('value')
        if measurement:
            if measurement['source_sha256'] != hashes['native_parking_history.json'] or measurement['source_frames'] != 600 or measurement['rest_frames'] != 80 or measurement['legal_verdict'] is not None:
                raise ValueError('Parked body measurement differs: ' + suffix)
        if exception:
            context = attempt / 'exception_context.json'
            if not context.is_file() or exception['source_sha256'] != sha(context) or exception['requested_polarity'] not in ('absent', 'present'):
                raise ValueError('Exception source polarity differs: ' + suffix)
        cases[suffix] = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'], 'source_sha256': hashes, 'engineering_knobs': config['engineering_knobs'], 'camera_profile': cameras, 'distance_m': measurement['nearest_parked_body_distance_m'] if measurement else None, 'sampled_relation': measurement['sampled_relation'] if measurement else None, 'requested_exception_polarity': exception['requested_polarity'] if exception else None, 'exception_source_sha256': exception['source_sha256'] if exception else None}
    for group, members in EXPECTED.items():
        anchor = cases[members[0]]
        for member in members[1:]:
            other = cases[member]
            for key in ('engineering_knobs', 'camera_profile'):
                if anchor[key] != other[key]:
                    raise ValueError('Fixed comparison condition changed: ' + group + '/' + key)
            if group in ('witness_comparison', 'numeric_1_comparison', 'exception_1_comparison') and anchor['source_sha256']['road_geometry.json'] != other['source_sha256']['road_geometry.json']:
                raise ValueError('Fixed intersection geometry changed: ' + group)
    if [round(cases[s]['distance_m'], 3) for s in EXPECTED['witness_comparison']] != [15.4, 3.9]:
        raise ValueError('Witness parked-body contrast changed')
    if [round(cases[s]['distance_m'], 3) for s in EXPECTED['numeric_1_comparison']] != [3.9, 4.572, 5.4] or cases['numeric_1_1']['sampled_relation'] != 'boundary_unresolved':
        raise ValueError('Below/at/above 15-foot contrast changed')
    for group in ('exception_1_comparison', 'exception_2_comparison', 'exception_3_comparison'):
        members = EXPECTED[group]
        if [cases[s]['requested_exception_polarity'] for s in members] != ['absent', 'present'] or cases[members[0]]['exception_source_sha256'] == cases[members[1]]['exception_source_sha256']:
            raise ValueError('Exception source contrast changed: ' + group)
    return {'format': 'c110454-a11-selected-comparison-audit', 'passed': True, 'runtime_manifest_sha256': current, 'comparisons': {key: list(value) for key, value in EXPECTED.items()}, 'cases': cases, 'original_native_observed': False, 'physical_acceptance_claimed': False, 'legal_verdict_claimed': False, 'limitations': 'Source-bound synthetic CPU contrast only; original pixels, physical completion, statutory applicability and exact boundary judgment require independent Native review'}

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--corrupt-source', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    report = audit(args.corrupt_source)
    if args.output.exists():
        raise ValueError('Retain previous comparison output')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'passed': True, 'comparison_count': len(report['comparisons']), 'audit_sha256': sha(args.output)}))
