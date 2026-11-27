"""Independently compare two saved taxi analyses without making a legal finding."""
import argparse
import hashlib
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent.parent
SOURCES = ('yellow-zone-native.jsonl', 'observed-passenger-activity.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'road.xodr', 'yellow-road.xodr',
           'sign-authority-pending.json', 'taxicab-review.json', 'sign-review.json',
           'passenger-purpose-review.json', 'ordinary-rules-review.json',
           'commercial-status-review.json',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
           'driver_reference.mkv')
FREIGHT_SOURCES = ('freight-native.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                   'road.xodr', 'yellow-freight-road.xodr',
                   'sign-authority-pending.json', 'commercial-status-review.json',
                   'sign-review.json', 'freight-purpose-review.json',
                   'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                   'driver_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def inspect(folder, expected_kind):
    folder = Path(folder).resolve()
    manifest = read(folder / 'source-manifest.json')
    bound = manifest.get('sha256', {})
    if manifest.get('source_kind') != expected_kind or set(bound) != set(SOURCES):
        raise ValueError('Exact independent taxi source seal differs')
    if expected_kind == 'original_native':
        capture_seal = read(folder / 'capture-seal.json')
        if (manifest.get('capture_seal_sha256') != sha(folder / 'capture-seal.json') or
                capture_seal.get('provenance_kind') != 'native' or
                capture_seal.get('diagnostic_fixture') is not False):
            raise ValueError('Original taxi Native capture binding differs')
    for name in SOURCES:
        if not (folder / name).is_file() or sha(folder / name) != bound[name]:
            raise ValueError('Changed independently sealed taxi source: ' + name)
    config = read(folder / 'config.json')
    measured = read(folder / 'analysis-report.json')['measurements']['taxi_yellow_zone_measurement']['value']
    result = read(folder / 'result.json')
    if (result.get('case_id') != config.get('case_id') or
            measured.get('case_id') != config.get('case_id') or
            result.get('measured_values') != measured or
            measured.get('source_kind') != expected_kind or
            measured.get('frames') != 600):
        raise ValueError('Selected taxi measurement/source identity differs')
    native = rows(folder / 'yellow-zone-native.jsonl')
    activity = rows(folder / 'observed-passenger-activity.jsonl')
    if len(native) != 600 or len(activity) != 600:
        raise ValueError('Full independent taxi frame join required')
    for index, (n, a) in enumerate(zip(native, activity)):
        if (n.get('video_frame') != index or a.get('video_frame') != index or
                a.get('native_frame') != n.get('native_frame') or
                a.get('source_kind') != expected_kind or
                a.get('observed_purpose') != config['requested_purpose']):
            raise ValueError('Independent taxi activity frame join differs')
    return {'case_id': config['case_id'], 'config': config, 'measurement': measured,
            'sign': read(folder / 'sign-review.json'),
            'yellow_road_sha256': sha(folder / 'yellow-road.xodr'),
            'readback_road_sha256': sha(folder / 'road.xodr'),
            'source_manifest_sha256': sha(folder / 'source-manifest.json')}


def inspect_freight(folder, expected_kind):
    folder = Path(folder).resolve()
    manifest = read(folder / 'source-manifest.json')
    bound = manifest.get('sha256', {})
    if manifest.get('source_kind') != expected_kind or set(bound) != set(FREIGHT_SOURCES):
        raise ValueError('Exact independently sealed freight source set differs')
    if expected_kind == 'original_native':
        seal = read(folder / 'capture-seal.json')
        if (manifest.get('capture_seal_sha256') != sha(folder / 'capture-seal.json') or
                seal.get('provenance_kind') != 'native' or seal.get('diagnostic_fixture') is not False):
            raise ValueError('Original freight Native capture binding differs')
    for name in FREIGHT_SOURCES:
        if not (folder / name).is_file() or sha(folder / name) != bound[name]:
            raise ValueError('Changed independently sealed freight source: ' + name)
    config = read(folder / 'config.json')
    measured = read(folder / 'analysis-report.json')['measurements']['freight_yellow_zone_measurement']['value']
    result = read(folder / 'result.json')
    if (result.get('case_id') != config.get('case_id') or
            measured.get('case_id') != config.get('case_id') or
            result.get('measured_values') != measured or
            measured.get('source_kind') != expected_kind or measured.get('frames') != 600):
        raise ValueError('Selected freight measurement/source identity differs')
    native = rows(folder / 'freight-native.jsonl')
    if len(native) != 600:
        raise ValueError('Full independent freight Native interval required')
    commercial = read(folder / 'commercial-status-review.json')
    purpose = read(folder / 'freight-purpose-review.json')
    if (commercial.get('taxi_actor_id') != native[0].get('taxi_actor_id') or
            purpose.get('cargo_actor_id') != native[0].get('cargo_actor_id') or
            purpose.get('observed_purpose') != measured.get('observed_purpose')):
        raise ValueError('Freight actor or purpose review detached from Native source')
    for index, row in enumerate(native):
        if (row.get('video_frame') != index or
                row.get('taxi_actor_id') != commercial['taxi_actor_id'] or
                row.get('cargo_actor_id') != purpose['cargo_actor_id'] or
                row.get('requested_purpose') != config['requested_purpose'] or
                row.get('source_kind') != expected_kind):
            raise ValueError('Independent freight actor/frame join differs')
    return {'case_id': config['case_id'], 'config': config,
            'measurement': measured, 'sign': read(folder / 'sign-review.json'),
            'commercial': commercial,
            'yellow_road_sha256': sha(folder / 'yellow-freight-road.xodr'),
            'readback_road_sha256': sha(folder / 'road.xodr'),
            'source_manifest_sha256': sha(folder / 'source-manifest.json')}


def audit(comparison, left_folder, right_folder, synthetic_fixture=False):
    kind = 'synthetic_cpu_fixture' if synthetic_fixture else 'original_native'
    plan = read(PACKAGE / 'case-plan.json')
    item = next((c for c in plan['comparisons']
                 if c['comparison_id'] == comparison), None)
    if item is None or len(item['case_ids']) != 2:
        raise ValueError('Exact taxi comparison missing')
    freight = '__freight_' in comparison
    reader = inspect_freight if freight else inspect
    left, right = reader(left_folder, kind), reader(right_folder, kind)
    if [left['case_id'], right['case_id']] != item['case_ids']:
        raise ValueError('Taxi comparison case order/identity differs')
    a, b = left['config'], right['config']
    fixed = (('assignment_id', 'cell_id', 'law_id', 'actor', 'duration_s',
              'rate_hz', 'frames', 'cargo_blueprint_filter', 'taxi_stop_x_m',
              'cameras', 'sign_source_status', 'commercial_classification') if freight else
             ('assignment_id', 'cell_id', 'law_id', 'actor', 'duration_s',
              'rate_hz', 'frames', 'taxi_blueprint_filter', 'taxi_stop_x_m',
              'cameras', 'sign_source_status', 'ordinary_rules_outside_hours'))
    if (any(a.get(key) != b.get(key) for key in fixed) or
            left['yellow_road_sha256'] != right['yellow_road_sha256'] or
            left['readback_road_sha256'] != right['readback_road_sha256'] or
            left['sign'] != right['sign'] or
            (freight and left['commercial'] != right['commercial'])):
        raise ValueError('Taxi comparison changed a fixed condition')
    if freight:
        expected = ('loading_light_express' if comparison.endswith('__freight_load_comparison')
                    else 'unloading_light_express' if comparison.endswith('__freight_unload_comparison')
                    else None)
        if (expected is None or a['civil_start_local'] != b['civil_start_local'] or
                a['requested_purpose'] != 'waiting_without_transfer' or
                b['requested_purpose'] != expected):
            raise ValueError('Freight purpose comparison changed clock or purpose pair')
        difference = 'requested_cargo_transfer_direction'
    elif comparison.endswith('__hours_comparison'):
        if (a['requested_purpose'] != b['requested_purpose'] or
                a['civil_start_local'] == b['civil_start_local'] or
                a['civil_start_local'][11:16] != '10:00' or
                b['civil_start_local'][11:16] != '18:00'):
            raise ValueError('Taxi hours comparison changed purpose or clock pair')
        difference = 'civil_clock_hour'
    else:
        expected = ('loading_passengers' if comparison.endswith('__loading_comparison')
                    else 'unloading_passengers' if comparison.endswith('__unloading_comparison')
                    else None)
        if (expected is None or a['civil_start_local'] != b['civil_start_local'] or
                a['requested_purpose'] != 'waiting_for_passengers' or
                b['requested_purpose'] != expected):
            raise ValueError('Taxi purpose comparison changed clock or purpose pair')
        difference = 'requested_passenger_purpose'
    return {'format': 'c150173-independent-saved-comparison-v1',
            'comparison_id': comparison, 'case_ids': item['case_ids'],
            'source_kind': kind, 'fixed_conditions_verified': list(fixed) +
                ['authored_and_readback_road', 'reviewed_sign'],
            'deliberate_difference': difference,
            'measurements': [left['measurement'], right['measurement']],
            'source_manifest_sha256': [left['source_manifest_sha256'],
                                       right['source_manifest_sha256']],
            'physical_or_legal_acceptance': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', required=True)
    parser.add_argument('--right', required=True)
    parser.add_argument('--synthetic-fixture', action='store_true')
    parser.add_argument('--output')
    args = parser.parse_args()
    report = audit(args.comparison, args.left, args.right, args.synthetic_fixture)
    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'comparison_id': report['comparison_id'],
                      'source_kind': report['source_kind'],
                      'deliberate_difference': report['deliberate_difference']}))
