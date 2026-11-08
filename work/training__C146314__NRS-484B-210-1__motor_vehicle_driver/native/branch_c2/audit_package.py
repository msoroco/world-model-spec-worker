"""Independently recompute paragraph (c)(2) copied topology and requests."""
import hashlib
import json
import math
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CASE = HERE.parent.parent
ROOT = CASE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit():
    construction = read(HERE/'manifest.json')
    offline = read(HERE/'offline/manifest.json')
    proof = read(HERE/'offline/proof-compatibility.json')
    assignment = ROOT/'inputs'/CASE.name/'assignment.json'
    plan = CASE/'case-plan.json'
    if (construction['assignment_sha256'] != sha(assignment) or
        construction['case_plan_sha256'] != sha(plan) or
        construction['capture_sha256'] != sha(HERE/'capture.py') or
        construction['measurement_contract_sha256'] != sha(HERE/'measurement-contract.json') or
        construction['saved_sha256'] != sha(HERE/'saved.py') or
        construction['fixture_raw_sha256'] != sha(HERE/'fixture_raw.py') or
        construction['route_fallbacks_sha256'] != sha(HERE/'route_fallbacks.py') or
        offline['construction_sha256'] != sha(HERE/'manifest.json') or
        proof['positives'] != 16 or proof['negatives'] != 40 or
        len(offline['entries']) != 8):
        raise ValueError('c2 construction provenance')
    source = read(plan)['source_law']['text']
    if ('not marked as a traffic lane; or (2)' not in source or
        'does not travel through an intersection or past any private way' not in source):
        raise ValueError('disjunctive frozen source')
    tracks = {}
    for entry in offline['entries']:
        witness = entry['case_id'].split('__')[-1]
        candidate = entry['candidate_id']
        bundle = HERE/entry['bundle']
        source_files = {
            'assignment-source.json': assignment,
            'case-plan.json': plan,
            'unmarked-pass.xodr': HERE/'roads'/(witness+'.xodr'),
            'config.json': HERE/'drafts'/witness/candidate/'config.json',
            'requested-tracks.jsonl': HERE/'drafts'/witness/candidate/'requested-tracks.jsonl',
            'build.py': HERE/'build.py', 'check.py': HERE/'check.py',
            'capture.py': HERE/'capture.py',
            'measurement-contract.json': HERE/'measurement-contract.json',
            'saved.py': HERE/'saved.py', 'fixture_raw.py': HERE/'fixture_raw.py',
            'route_fallbacks.py': HERE/'route_fallbacks.py'}
        if set(source_files) != set(entry['file_sha256']):
            raise ValueError('copy set')
        for name, path in source_files.items():
            if sha(bundle/name) != sha(path) or entry['file_sha256'][name] != sha(path):
                raise ValueError('copied byte '+name)
        root = ET.parse(bundle/'unmarked-pass.xodr').getroot()
        private = witness == 'exception_3_1'
        if len(root.findall('./road')) != (2 if private else 1) or \
           (root.find('./junction') is not None) != private or \
           construction['road_sha256_by_witness'][witness] != sha(bundle/'unmarked-pass.xodr'):
            raise ValueError('private-way topology difference')
        cfg = read(bundle/'config.json')
        track = rows(bundle/'requested-tracks.jsonl')
        speed = 7.5 if candidate == 'fallback1' else 8
        stop = 35 if candidate == 'fallback3' else None
        if len(track) != 240 or cfg['private_way_requested'] != private or \
           cfg['requested_c1_over_200ft'] is not True or \
           cfg['actual_private_way_passed_observed'] is not False:
            raise ValueError('c2 request policy')
        for i, row in enumerate(track):
            t = (i+1)/20
            x = min(stop or 300, 5+speed*t)
            blend = max(0, min(1, (x-6.2)/5, (78.8-x)/5))
            if (row['frame'] != i or row['time_s'] != t or
                not math.isclose(row['ego_x_m'], x, abs_tol=1e-6) or
                not math.isclose(row['ego_y_m'], -1.75-3.5*blend, abs_tol=1e-6) or
                not math.isclose(row['lead_x_m'], 30+4*t, abs_tol=1e-6) or
                row['private_way_x_m'] != 50 or
                row['private_way_requested'] != private or
                row['actual_private_way_passed_observed'] is not False):
                raise ValueError(f'independent c2 row {i}')
        tracks[(witness, candidate)] = track
    if len(tracks) != 8:
        raise ValueError('c2 coverage')
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        a = tracks[('exception_3_1', candidate)]
        b = tracks[('exception_3_2', candidate)]
        for x, y in zip(a, b):
            for key in ('frame', 'time_s', 'ego_x_m', 'ego_y_m',
                        'lead_x_m', 'lead_y_m', 'private_way_x_m'):
                if x[key] != y[key]:
                    raise ValueError('c2 controlled pair '+key)
            if x['private_way_requested'] is not True or \
               y['private_way_requested'] is not False:
                raise ValueError('c2 pair spur variable')
    result = {'format': 'c146314-paragraph-c2-independent-audit-v1',
              'bundles': 8, 'controlled_pairs': 4, 'rows_recomputed': 1920,
              'private_way_x_m': 50, 'requested_unmarked_excursion_m': 65,
              'copied_positives': 16, 'rejected_negatives': 40,
              'private_way_native_readback_observed': False,
              'delivery_ready': False}
    (HERE/'offline/package-audit.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    print(json.dumps(audit()))
