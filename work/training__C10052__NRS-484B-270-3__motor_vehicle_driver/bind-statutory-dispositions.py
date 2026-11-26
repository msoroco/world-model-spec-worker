"""Bind each selected statutory topic to a distinct saved source observation.

These outputs carry diagnostic observations and an explicit original-evidence gap.
They are not findings that a legal duty or exception was satisfied.
"""
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PLAN = ROOT / 'case-plan.json'
MANIFEST = ROOT / 'execution-manifest.json'

FIELDS = {
    1: ('rider_type', 'rider_actor_id', 'clearance_s', 'simultaneous_conflict_frames'),
    2: ('rider_type', 'rider_actor_id', 'clearance_s', 'simultaneous_conflict_frames'),
    3: ('rider_type', 'rider_actor_id', 'clearance_s', 'simultaneous_conflict_frames'),
    4: ('first_pedestrian_conflict_frame', 'last_pedestrian_conflict_frame',
        'first_ego_conflict_frame', 'simultaneous_conflict_frames'),
    5: ('moving_entry_measured', 'first_moving_entry_native_frame', 'moving_occupied_frames'),
    6: ('max_stopped_overlap_m2', 'stop_duration_s'),
    7: ('mean_stopped_overlap_m2', 'stop_duration_s', 'observed_exception_status'),
    8: ('park_control_candidate', 'held_duration_s', 'max_held_facility_overlap_m2'),
    9: ('bicycle_lane_occupied_frames',),
    10: ('first_facility_entry_native_frame', 'first_alley_footprint_native_frame',
         'facility_to_alley_gap_s', 'simultaneous_moving_overlap_frames'),
    11: ('fault_readback_frames', 'propulsion_test_displacement_m',
         'bicycle_lane_occupied_frames_100_240'),
    12: ('active_conflict_actor_frames', 'counterfactual_straight_collision_frames',
         'actual_collision_frames', 'bicycle_lane_occupied_frames'),
    13: ('duty_active_frames', 'duty_occupied_frames', 'bicycle_lane_occupied_frames'),
    14: ('direction_active_frames', 'direction_response_frames',
         'bicycle_lane_occupied_frames'),
    15: ('incident_active_frames', 'incident_occupied_frames',
         'bicycle_lane_occupied_frames'),
    16: ('sidewalk_obstructed', 'buffer_impassable', 'bounded_monotonic_path',
         'first_sidewalk_return_frame', 'return_gap_after_obstacle_frames'),
}

KEY = lambda index: f'statutory_disposition_{index:02d}_context'


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def target_finalizer(construction):
    files = construction['files']
    specialised = [f for f in files if f['path'].startswith('finalize_') and f['path'].endswith('.py')]
    return specialised[0] if specialised else next(f for f in files if f['path'] == 'finalize.py')


def observed_fields(index, value):
    if index == 5 and 'moving_entry_measured' not in value:
        return ('first_facility_entry_native_frame', 'simultaneous_moving_overlap_frames')
    if index == 9 and 'bicycle_lane_occupied_frames' not in value:
        return ('simultaneous_moving_overlap_frames',) if 'simultaneous_moving_overlap_frames' in value else ('moving_occupied_frames',)
    if index == 10 and 'first_alley_footprint_native_frame' not in value:
        return ('first_moving_entry_native_frame', 'first_entry_alley_footprint_gap_m',
                'moving_facility_alley_footprint_overlap_frames')
    return FIELDS[index]


HELPER = '''\n\ndef statutory_disposition_context(attempt, index, topic, base, fields, inputs):
    """Expose a separate source-bound diagnostic topic without a legal verdict."""
    import hashlib
    from pathlib import Path
    attempt = Path(attempt)
    value = base['value']
    observed = {name: value[name] for name in fields if name in value}
    if not observed:
        raise ValueError('No measured fields for statutory disposition: ' + str(index))
    sources = {}
    for name in inputs:
        path = attempt / name
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {'method': 'statutory_disposition_context',
            'value': {'disposition_index': index, 'source_topic': topic,
                      'diagnostic_observation': observed,
                      'original_native_review_required': True,
                      'legal_verdict_claimed': False},
            'sources': sources}
'''


def main():
    plan = json.loads(PLAN.read_text())
    manifest = json.loads(MANIFEST.read_text())
    dispositions = plan['requirement_dispositions']
    assert len(dispositions) == 17
    for case in manifest['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        selected = [i for i, row in enumerate(dispositions) if i and case['case_id'] in row['case_ids']]
        contract_path = ROOT / case['measurement_contract']
        contract = json.loads(contract_path.read_text())
        base = contract['requirements'][0]
        assert base['disposition_index'] == 0, suffix
        assert len(contract['requirements']) == 1, suffix
        current_report = json.loads((contract_path.parent / 'analysis.log').read_text().splitlines()[-1])
        value = current_report['measurements'][base['output_key']]['value']
        additions = []
        for i in selected:
            row = dispositions[i]
            fields = observed_fields(i, value)
            assert all(field in value for field in fields), (suffix, i, fields, value.keys())
            additions.append((i, row['source'], fields, base['inputs']))
            contract['requirements'].append({
                'disposition_index': i, 'requirement': row['requirement'],
                'source': row['source'], 'kind': 'sourced_context',
                'method': 'statutory_disposition_context', 'value_type': 'object',
                'output_key': KEY(i), 'inputs': base['inputs'],
            })
        write_json(contract_path, contract)
        for construction_rel, owner in [(case['construction'], case)] + [
            (candidate['construction'], candidate) for candidate in case['candidates']]:
            path = ROOT / construction_rel
            construction = json.loads(path.read_text())
            finalizer = target_finalizer(construction)
            code = finalizer['content']
            assert 'def statutory_disposition_context(' not in code, (suffix, construction_rel)
            marker = '\ndef finalize('
            if marker not in code:
                marker = '\ndef finalize_full_attempt('
            assert marker in code, (suffix, construction_rel)
            code = code.replace(marker, HELPER + marker, 1)
            calls = '\n'.join(
                '    report["measurements"][%r] = statutory_disposition_context('
                'attempt, %d, %r, report["measurements"][%r], %r, %r)' %
                (KEY(i), i, topic, base['output_key'], tuple(fields), tuple(inputs))
                for i, topic, fields, inputs in additions)
            marker = '    output.write_text('
            assert marker in code, (suffix, construction_rel)
            code = code.replace(marker, calls + '\n' + marker, 1)
            ast.parse(code)
            finalizer['content'] = code
            write_json(path, construction)
            owner['construction_sha256'] = sha(path)
    for row in dispositions:
        row['status'] = 'selected_required'
    write_json(PLAN, plan)
    write_json(MANIFEST, manifest)
    print('Bound 17 dispositions across 24 selected cases and their candidates')


if __name__ == '__main__':
    main()
