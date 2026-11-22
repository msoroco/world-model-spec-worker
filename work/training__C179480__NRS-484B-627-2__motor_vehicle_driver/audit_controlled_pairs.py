"""Audit synthetic source-channel isolation for the four draft stop cases.

This verifies diagnostic construction and saved processing only. It cannot decide
whether traffic was impeded or either statutory exception applies in a recording.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'candidate-matrix-manifest.json'
MATRIX = HERE / 'base-current-candidate-matrix-audit.json'
ASSETS = ROOT / '.runtime-work/c179480-native-sweep/saved-base-current'
NAMES = ('reference', 'contrast', 'safe_operation_stop', 'law_required_stop')
CHOICES = ('primary', 'fallback1', 'fallback2', 'fallback3')
PAIRS = (('reference', 'contrast', 'roadway_placement'),
         ('reference', 'safe_operation_stop', 'designated_hazard'),
         ('reference', 'law_required_stop', 'designated_control'))


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def channel(name, choice, key):
    path = ASSETS / f'{HERE.name}__{name}' / choice / 'v0001/analysis/channels' / f'{key}.jsonl'
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    require(len(rows) == 600, f'{name}/{choice}/{key}: expected 600 source rows')
    require(all(row['time_s'] == i / 20 for i, row in enumerate(rows)),
            f'{name}/{choice}/{key}: timestamp join changed')
    return [row['value'] for row in rows], sha(path)


def audit():
    manifest = read(MANIFEST)
    matrix = read(MATRIX)
    require(matrix['passed'] is True and matrix['manifest_sha256'] == sha(MANIFEST),
            'Current exact candidate matrix is not bound')
    ids = {row['case_id'].rsplit('__', 1)[-1] for row in manifest['cases']}
    require(ids == set(NAMES), 'Case inventory changed')
    bound = {(row['case_id'].rsplit('__', 1)[-1], row['candidate_id']): row
             for row in matrix['rows']}
    require(set(bound) == {(n, c) for n in NAMES for c in CHOICES},
            'Candidate proof inventory incomplete')
    rows = []
    for choice in CHOICES:
        for left, right, difference in PAIRS:
            evidence = {}
            for name in (left, right):
                processing = HERE / bound[name, choice]['artifacts']['processing']['path']
                require(sha(processing) == bound[name, choice]['artifacts']['processing']['sha256'],
                        f'{name}/{choice}: processing receipt changed')
                data = {}
                hashes = {}
                for key in ('ego_stop_history', 'following_actor_gap_history',
                            'following_actor_deceleration', 'following_actor_stop_history',
                            'ego_lane_footprint', 'traffic_effect_evidence',
                            'hazard_actor_state', 'ego_hazard_gap_history',
                            'governing_control_readback'):
                    data[key], hashes[key] = channel(name, choice, key)
                evidence[name] = (data, hashes)
            a, b = evidence[left][0], evidence[right][0]
            for key in ('ego_stop_history', 'following_actor_gap_history',
                        'following_actor_deceleration', 'following_actor_stop_history'):
                require(a[key] == b[key], f'{choice}/{difference}: fixed {key} changed')
            require(all(x['normal_reasonable_movement_impeded'] ==
                        'independent_original_source_review_required'
                        for x in a['traffic_effect_evidence'] + b['traffic_effect_evidence']),
                    f'{choice}/{difference}: legal traffic effect asserted')
            if difference == 'roadway_placement':
                require(all(x['driving_lane_overlap'] for x in a['ego_lane_footprint']) and
                        all(not x['driving_lane_overlap'] for x in b['ego_lane_footprint']),
                        f'{choice}: roadway placement contrast absent')
                for key in ('hazard_actor_state', 'ego_hazard_gap_history',
                            'governing_control_readback'):
                    require(a[key] == b[key], f'{choice}: noncompared {key} changed')
            elif difference == 'designated_hazard':
                require(a['ego_lane_footprint'] == b['ego_lane_footprint'],
                        f'{choice}: hazard pair lane footprint changed')
                require(all(x.get('absence_claimed') is False for x in a['hazard_actor_state']) and
                        all(x.get('on_driving_lane') is True for x in b['hazard_actor_state']),
                        f'{choice}: designated hazard source absent')
                require(a['governing_control_readback'] == b['governing_control_readback'],
                        f'{choice}: hazard pair control changed')
            else:
                require(a['ego_lane_footprint'] == b['ego_lane_footprint'],
                        f'{choice}: control pair lane footprint changed')
                require(all(x.get('absence_claimed') is False for x in a['governing_control_readback']) and
                        any(x.get('ego_associated_control_id') == x.get('control_actor_id') and
                            x.get('control_state') == 'TrafficLightState.Red'
                            for x in b['governing_control_readback']),
                        f'{choice}: associated red control source absent')
            rows.append({'candidate_id': choice, 'cases': [left, right],
                         'diagnostic_difference': difference,
                         'channel_sha256': {name: evidence[name][1] for name in (left, right)},
                         'synthetic_source_isolation_passed': True})
    target = HERE / 'update096-controlled-pair-audit.json'
    target.write_text(json.dumps({'format': 'c179480-controlled-pair-cpu-diagnostic-v1',
        'manifest_sha256': sha(MANIFEST), 'candidate_matrix_sha256': sha(MATRIX),
        'passed': True, 'pairs': rows, 'physical_acceptance_claimed': False,
        'legal_acceptance_claimed': False}, indent=2, sort_keys=True) + '\n')
    return target


if __name__ == '__main__':
    print(audit())
