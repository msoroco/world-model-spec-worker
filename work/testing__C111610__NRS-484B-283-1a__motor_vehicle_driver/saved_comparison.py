"""Independent saved-source comparison for the five C111610 planned pairs.

The audit reopens both sealed attempts. Its result is a source comparison, not
proof of physical provenance, visibility, danger, or a legal right-of-way verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

import saved_measurement as measurement


class ComparisonError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ComparisonError(message)


def read_original(attempt, index, name):
    return measurement.read_sealed(attempt, index, name)[0]


def audit_pair(plan_path, comparison_id, left_attempt, left_scene, right_attempt, right_scene, output):
    plan = json.loads(Path(plan_path).read_text(encoding='utf-8'))
    comparisons = [row for row in plan['comparisons'] if row['comparison_id'] == comparison_id]
    require(len(comparisons) == 1, 'unknown or duplicate comparison')
    declared = comparisons[0]
    scenes = [json.loads(Path(path).read_text(encoding='utf-8')) for path in (left_scene, right_scene)]
    require([row['case_id'] for row in scenes] == declared['case_ids'], 'comparison case/order mismatch')
    attempts = [Path(left_attempt), Path(right_attempt)]
    require(attempts[0].resolve() != attempts[1].resolve(), 'distinct original attempts required')
    with tempfile.TemporaryDirectory() as temp:
        measured = [measurement.process(attempts[i], (left_scene, right_scene)[i],
                                        Path(temp) / f'{i}.json') for i in range(2)]
    indices = [json.loads((attempt / 'source-index.json').read_text(encoding='utf-8')) for attempt in attempts]
    sites = [read_original(attempts[i], indices[i], 'site') for i in range(2)]
    egos = [read_original(attempts[i], indices[i], 'ego') for i in range(2)]
    people = [read_original(attempts[i], indices[i], 'pedestrian') for i in range(2)]
    exceptions = [read_original(attempts[i], indices[i], 'exception_review') for i in range(2)]
    for key in ('law_id', 'cell_id', 'actor', 'turn_direction', 'ego_blueprint_id',
                'pedestrian_blueprint_id', 'rate_hz', 'duration_s', 'camera_contract',
                'engineering_throttle'):
        require(scenes[0].get(key) == scenes[1].get(key), 'fixed scene condition changed: ' + key)
    require(measured[0]['frame_count'] == measured[1]['frame_count'] == 600,
            'common 600-frame contract changed')
    require(measured[0]['source_index_sha256'] != measured[1]['source_index_sha256'],
            'source index reused across compared attempts')
    # Device-state pairs change only the device inventory; all other pairs share
    # the complete site packet, including the original device survey.
    if declared['variable_key'] == 'official_device_condition':
        site_fixed = [{k:v for k,v in site.items() if k != 'official_devices'} for site in sites]
    else:
        site_fixed = sites
    require(site_fixed[0] == site_fixed[1], 'fixed original site/turn/crosswalk changed')
    require(exceptions[0]['status'] == exceptions[1]['status'], 'exception status changed')
    require(exceptions[0]['source_refs'] == exceptions[1]['source_refs'], 'exception review source changed')
    require(egos[0] == egos[1], 'fixed original ego motion/control changed')
    require({row['actor_id'] for row in people[0]} == {row['actor_id'] for row in people[1]},
            'pedestrian identity changed')
    require({row['classification'] for row in people[0]} == {row['classification'] for row in people[1]},
            'pedestrian classification changed')
    observations = [row['measurements'] for row in measured]
    key = declared['variable_key']
    if key == 'pedestrian_half':
        values = [sum(r['pedestrian_in_crosswalk'] and r['pedestrian_on_destination_half'] for r in rows)
                  for rows in observations]
    elif key == 'crosswalk_position':
        values = [sum(r['pedestrian_in_crosswalk'] for r in rows) for rows in observations]
    elif key == 'opposite_half_proximity':
        require(all(any(r['pedestrian_in_crosswalk'] and not r['pedestrian_on_destination_half']
                        for r in rows) for rows in observations), 'opposite-half observation missing')
        values = [min(r['pedestrian_to_ego_distance_m'] for r in rows) for rows in observations]
    elif key == 'official_device_condition':
        values = [row['summary']['measured_device_condition'] for row in measured]
    else:
        raise ComparisonError('unsupported declared comparison variable')
    require(values[0] != values[1], 'declared measured variable did not differ')
    if key == 'official_device_condition':
        require(all(row['summary']['planned_device_condition_matches'] for row in measured),
                'original device state disagrees with planned condition')
    result = {
        'format': 'c111610-saved-comparison-v1', 'comparison_id': comparison_id,
        'case_ids': declared['case_ids'], 'variable_key': key, 'measured_values': values,
        'source_index_sha256': [row['source_index_sha256'] for row in measured],
        'fixed_original_site_ego_exception_checked': True,
        'physical_source_verified': False, 'legal_judgment': 'unresolved',
    }
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('plan', 'comparison-id', 'left-attempt', 'left-scene',
                 'right-attempt', 'right-scene', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    audit_pair(args.plan, args.comparison_id, args.left_attempt, args.left_scene,
               args.right_attempt, args.right_scene, args.output)
