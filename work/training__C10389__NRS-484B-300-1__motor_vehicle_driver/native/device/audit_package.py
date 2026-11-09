"""Independent copied-byte and request-geometry audit for C10389."""
import hashlib
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]
POLICIES = {'primary': (8.0, 'standard', 'target'),
            'fallback1': (5.0, 'standard', 'target'),
            'fallback2': (8.0, 'elevated_overview', 'target'),
            'fallback3': (8.0, 'standard', 'stop_before_device')}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit():
    construction = read(HERE / 'manifest.json')
    copied = read(HERE / 'offline' / 'manifest.json')
    proof = read(HERE / 'offline' / 'proof-compatibility.json')
    assignment = ROOT / 'inputs' / CASE.name / 'assignment.json'
    plan = CASE / 'case-plan.json'
    law = read(assignment)['law_record']['text']
    checks = {'assignment_sha256': assignment,
              'case_plan_sha256': plan,
              'road_sha256': HERE / 'alley-stop.xodr',
              'capture_sha256': HERE / 'capture.py',
              'measurement_contract_sha256': HERE / 'measurement-contract.json',
              'saved_sha256': HERE / 'saved.py',
              'fixture_raw_sha256': HERE / 'fixture_raw.py',
              'route_fallbacks_sha256': HERE / 'route_fallbacks.py'}
    if (read(plan)['source_law']['text'] != law or
            any(construction[key] != sha(path) for key, path in checks.items()) or
            copied['construction_sha256'] != sha(HERE / 'manifest.json') or
            proof['positives'] != 8 or proof['negatives'] != 56 or
            len(copied['entries']) != 8):
        raise ValueError('source, construction or compatibility proof')
    total = 0
    pairs = {}
    for entry in copied['entries']:
        suffix = entry['case_id'].split('__')[-1]
        candidate = entry['candidate_id']
        if suffix not in ('probe_1', 'probe_2') or candidate not in POLICIES:
            raise ValueError('case/candidate identity')
        bundle = HERE / entry['bundle']
        sources = {'assignment-source.json': assignment, 'case-plan.json': plan,
            'alley-stop.xodr': HERE / 'alley-stop.xodr',
            'config.json': HERE / 'drafts' / suffix / candidate / 'config.json',
            'requested-tracks.jsonl': HERE / 'drafts' / suffix / candidate /
                                      'requested-tracks.jsonl',
            'build.py': HERE / 'build.py', 'check.py': HERE / 'check.py',
            'capture.py': HERE / 'capture.py',
            'measurement-contract.json': HERE / 'measurement-contract.json',
            'saved.py': HERE / 'saved.py', 'fixture_raw.py': HERE / 'fixture_raw.py',
            'route_fallbacks.py': HERE / 'route_fallbacks.py'}
        if set(entry['file_sha256']) != set(sources):
            raise ValueError('copied file set')
        if any(sha(bundle / name) != sha(source) or
               entry['file_sha256'][name] != sha(source)
               for name, source in sources.items()):
            raise ValueError('copied source byte mismatch')
        cfg = read(bundle / 'config.json')
        track = rows(bundle / 'requested-tracks.jsonl')
        root = ET.parse(bundle / 'alley-stop.xodr').getroot()
        signal = root.find('./road/signals/signal')
        if (root.find('./road').get('id') != '389' or signal is None or
                signal.get('id') != '3891' or signal.get('type') != '206' or
                signal.get('s') != '50' or len(track) != 240):
            raise ValueError('independent OpenDRIVE/request cardinality')
        speed, camera, policy = POLICIES[candidate]
        obey = suffix == 'probe_1'
        if (cfg['source_text'] != law or cfg['requested_obey'] is not obey or
                cfg['requested_speed_mps'] != speed or
                cfg['camera_policy'] != camera or cfg['route_policy'] != policy or
                cfg['official_placement_verified'] is not False or
                cfg['original_native_observed'] is not False):
            raise ValueError('independent candidate controls')
        stopped = crossed = 0
        for i, row in enumerate(track):
            t = (i+1)/20
            reach = 39/speed
            if policy == 'stop_before_device':
                x = min(44, 5+speed*t)
                velocity = 0 if t >= reach else speed
            elif obey and reach <= t < reach+1:
                x, velocity = 44, 0
            elif obey and t >= reach+1:
                x, velocity = 44+speed*(t-reach-1), speed
            else:
                x, velocity = 5+speed*t, speed
            if (row['frame'] != i or row['time_s'] != t or
                    row['requested_ego_x_m'] != round(x, 6) or
                    row['requested_ego_y_m'] != -1.75 or
                    row['requested_speed_mps'] != velocity or
                    row['requested_road_id'] != 389 or
                    row['requested_lane_id'] != -1 or
                    row['requested_stop_line_x_m'] != 50 or
                    row['requested_stop_hold'] is not obey or
                    row['observed_device_obedience'] is not None):
                raise ValueError('independent request row')
            stopped += int(velocity == 0)
            crossed += int(x > 50)
            total += 1
        if policy == 'target' and (crossed == 0 or stopped != (20 if obey else 0)):
            raise ValueError('stop/pass semantic')
        if policy == 'stop_before_device' and (crossed != 0 or stopped == 0):
            raise ValueError('stop-before semantic')
        pairs.setdefault(candidate, {})[suffix] = (speed, camera, policy, len(track))
    if (len(pairs) != 4 or any(set(pair) != {'probe_1', 'probe_2'} or
                               pair['probe_1'] != pair['probe_2']
                               for pair in pairs.values())):
        raise ValueError('four controlled pairs')
    return {'format': 'c10389-device-independent-package-audit-v1',
            'copied_bundles': 8, 'controlled_pairs': 4,
            'rows_recomputed': total, 'positive': 8,
            'tamper_negative': 56, 'official_placement_verified': False,
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(audit()))
