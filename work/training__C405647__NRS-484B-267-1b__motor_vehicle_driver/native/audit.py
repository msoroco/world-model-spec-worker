"""Independent audit of the unselected 1(b) CPU construction."""
import copy
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
AID = HERE.parent.name
OUT = HERE / 'drafts'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def check_rows(authored, native, case):
    if len(authored) != 480 or len(native) != 480:
        raise ValueError('wrong frame count')
    for frame, (a, n) in enumerate(zip(authored, native)):
        if a['frame'] != frame or n['frame'] != frame or a['time_s'] != frame / 20:
            raise ValueError('broken frame join')
        if n['subject_request']['y_m'] != -a['subject_request']['y_m'] or n['approach_request']['y_m'] != -a['approach_request']['y_m']:
            raise ValueError('Native y reflection mismatch')
        if a['officer_direction_request'] or a['signed_shoulder_permission_request']:
            raise ValueError('exception context changed')
        if a['approach_authority_observed'] or not a['lamp_request']['qualification_unverified']:
            raise ValueError('unobserved authority or lamp claimed')
        if a['subject_request']['heading_deg'] != 0:
            raise ValueError('subject no longer parallel to authored edge')
        if a['subject_request']['y_m'] - 0.9 < -7:
            raise ValueError('authored body enters shoulder')
    end = authored[-1]['subject_request']
    if end['y_m'] != (-6.0 if case == 'reference' else -1.75):
        raise ValueError('wrong controlled endpoint')
    if authored[120]['subject_request']['speed_mps'] != 0 or end['x_m'] != 48:
        raise ValueError('stop request changed')
    catchup = next((i for i, row in enumerate(authored)
                    if row['approach_request']['x_m'] >= row['subject_request']['x_m'] - 4.5), None)
    edge = next((i for i, row in enumerate(authored)
                 if row['subject_request']['y_m'] <= -5.95), None)
    move = next((i for i, row in enumerate(authored)
                 if row['subject_request']['y_m'] < -1.751), None)
    fov = authored[0]['camera_fov_deg']
    visible = sum(abs(math.degrees(math.atan2(
        row['approach_request']['y_m'] + 10.0,
        row['approach_request']['x_m'] - 40.0)) - 90.0) <= fov / 2
                  for row in authored[:catchup])
    if catchup != 159 or (case == 'reference' and (edge is None or edge >= catchup)) or (case == 'contrast' and edge is not None):
        raise ValueError('approach/edge ordering changed')
    return {'edge_frame': edge, 'catchup_frame': catchup, 'motion_frame': move,
            'synthetic_frustum_frames': visible,
            'stop_frame': 120, 'outer_body_y_m': end['y_m'] - 0.9}


def audit():
    manifest = read(OUT / 'manifest.json')
    assignment = ROOT / 'inputs' / AID / 'assignment.json'
    plan = HERE.parent / 'case-plan.json'
    if manifest['assignment_sha256'] != sha(assignment) or manifest['case_plan_sha256'] != sha(plan):
        raise ValueError('source hash mismatch')
    if manifest['map_sha256'] != sha(OUT / 'road.xodr'):
        raise ValueError('map hash mismatch')
    root = ET.parse(OUT / 'road.xodr').getroot()
    roads = root.findall('road')
    if len(roads) != 1 or roads[0].attrib['junction'] != '-1' or roads[0].findall('signals/signal'):
        raise ValueError('authored road has unexpected junction or signal')
    lanes = [(x.attrib['id'], x.attrib['type'], float(x.find('width').attrib['a']))
             for x in roads[0].findall('./lanes/laneSection/right/lane')]
    if lanes != [('-1', 'driving', 3.5), ('-2', 'driving', 3.5), ('-3', 'shoulder', 2.5)]:
        raise ValueError('edge or shoulder map mismatch')
    expected = {(AID + '__' + c, v) for c in ('reference', 'contrast')
                for v in ('primary', 'fallback1', 'fallback2', 'fallback3')}
    if {(x['case_id'], x['candidate_id']) for x in manifest['cases']} != expected:
        raise ValueError('missing case/candidate')
    findings = []
    for variant in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        pair = []
        for case in ('reference', 'contrast'):
            folder = OUT / case / variant
            config = read(folder / 'config.json')
            entry = next(x for x in manifest['cases'] if x['case_id'] == AID + '__' + case and x['candidate_id'] == variant)
            if (entry['config_sha256'] != sha(folder / 'config.json') or
                entry['tracks_sha256'] != sha(folder / 'requested-tracks.jsonl') or
                entry['native_sha256'] != sha(folder / 'native-requests.jsonl') or
                config['map_sha256'] != manifest['map_sha256'] or
                config['status'] != 'unselected_cpu_draft' or
                config['physical_execution_or_legal_outcome_verified']):
                raise ValueError('package hash/status mismatch')
            authored = rows(folder / 'requested-tracks.jsonl')
            native = rows(folder / 'native-requests.jsonl')
            measured = check_rows(authored, native, case)
            if (measured['edge_frame'] != config['metrics']['edge_target_frame'] or
                measured['catchup_frame'] != config['metrics']['approach_catchup_frame'] or
                measured['synthetic_frustum_frames'] != config['metrics']['synthetic_front_lamp_frustum_frames_before_catchup']):
                raise ValueError('recorded metric mismatch')
            trigger = config['measured_trigger']
            if variant == 'primary':
                if trigger is not None:
                    raise ValueError('primary has fallback trigger')
            else:
                if (not trigger or not trigger['triggered'] or
                    trigger['source_sha256'] != entry['tracks_sha256'] or
                    trigger['measured_on_case'] != AID + '__reference'):
                    raise ValueError('fallback trigger unbound')
                expected_metric = {'fallback1': 'first_lateral_motion_frame',
                                   'fallback2': 'edge_target_frame',
                                   'fallback3': 'synthetic_front_lamp_frustum_frames_before_catchup'}[variant]
                if trigger['metric'] != expected_metric:
                    raise ValueError('fallback metric mismatch')
            pair.append(authored)
            findings.append({'case': case, 'variant': variant, **measured})
        if any(a['approach_request'] != b['approach_request'] or
               a['lamp_request'] != b['lamp_request'] or
               a['subject_request']['x_m'] != b['subject_request']['x_m']
               for a, b in zip(*pair)):
            raise ValueError('controlled pair changed context')
    sample = rows(OUT / 'reference' / 'primary' / 'requested-tracks.jsonl')
    native = rows(OUT / 'reference' / 'primary' / 'native-requests.jsonl')
    negatives = 0
    for mutation, message in (
        (lambda a, n: a.pop(), 'wrong frame count'),
        (lambda a, n: a[7].update(frame=8), 'broken frame join'),
        (lambda a, n: n[7]['subject_request'].update(y_m=-n[7]['subject_request']['y_m']), 'Native y reflection mismatch'),
        (lambda a, n: a[9].update(officer_direction_request=True), 'exception context changed'),
        (lambda a, n: a[9]['lamp_request'].update(qualification_unverified=False), 'unobserved authority or lamp claimed'),
        (lambda a, n: (a[479]['subject_request'].update(y_m=-7.2),
                       n[479]['subject_request'].update(y_m=7.2)), 'authored body enters shoulder'),
    ):
        a, n = copy.deepcopy(sample), copy.deepcopy(native)
        mutation(a, n)
        try:
            check_rows(a, n, 'reference')
        except ValueError as exc:
            if str(exc) != message:
                raise
            negatives += 1
        else:
            raise ValueError('negative mutation was accepted')
    result = {'format': 'c405647-1b-cpu-audit-v1', 'manifest_sha256': sha(OUT / 'manifest.json'),
              'source_sha256': sha(assignment), 'case_candidates': len(findings),
              'negative_mutations_rejected': negatives, 'findings': findings,
              'physical_observation_or_legal_verdict': False}
    (HERE / 'cpu-audit.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
