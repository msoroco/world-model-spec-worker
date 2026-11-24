"""Unselected 30-second signal-outage intersection requests and offline bundles."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[1]
SOURCE = ROOT / 'inputs' / CASE.name / 'assignment.json'
SOURCE_SHA = '8f4584097a04f11c2af5ccffe5a5a43e675b9160afea1d235cbf5ef735d2a7ae'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(case):
    if case not in ('controlled_1', 'controlled_2'):
        raise ValueError('unknown exact request')
    out = []
    for frame in range(600):
        ego_x = (-35 + .2 * min(frame, 100) + .2 * max(0, frame - 210)
                 if case == 'controlled_1' else -35 + .2 * frame)
        other_y = min(35, -35 + .2 * frame)
        out.append({'frame': frame, 'time_s': frame / 20,
                    'ego_center_xy_m': [round(min(35, ego_x), 6), -1.75],
                    'ego_front_x_m': round(min(35, ego_x) + 2, 6),
                    'other_center_xy_m': [1.75, round(other_y, 6)],
                    'signal_id': 'c111331-installed-uncovered-vehicular-head',
                    'signal_installed_requested': True,
                    'signal_uncovered_requested': True,
                    'signal_display_requested': 'inoperative_dark',
                    'marked_stop_line_x_m': -12,
                    'near_side_crosswalk_x_m': -9,
                    'intersection_entry_x_m': -6,
                    'other_intersection_entry_y_m': -6,
                    'source_kind': 'synthetic_scene_request',
                    'native_observed': False, 'legal_verdict': None})
    return out


CHECK = '''"""Exact copied-source and requested crossing timing check."""
import hashlib
import json
from pathlib import Path

HERE = Path.cwd()

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def check():
    cfg = json.loads((HERE / 'config.json').read_text())
    assignment = json.loads((HERE / 'assignment-source.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if (cfg['assignment_sha256'] != sha(HERE / 'assignment-source.json') or
            cfg['plan_sha256'] != sha(HERE / 'case-plan.json') or
            cfg['rows_sha256'] != sha(HERE / 'request.jsonl') or
            assignment['law']['text'] != plan['source_law']['text'] or
            assignment['cell']['cell_id'] != 'C111331' or
            assignment['cell']['control'] != 'traffic_light'):
        raise ValueError('source or law binding differs')
    rows = [json.loads(line) for line in (HERE / 'request.jsonl').read_text().splitlines()]
    if len(rows) != 600:
        raise ValueError('full 600-frame request required')
    positions = []
    for i, row in enumerate(rows):
        if row['frame'] != i or row['time_s'] != i / 20:
            raise ValueError('frame/time join differs')
        if (row['signal_id'] != 'c111331-installed-uncovered-vehicular-head' or
                row['signal_installed_requested'] is not True or
                row['signal_uncovered_requested'] is not True or
                row['signal_display_requested'] != 'inoperative_dark' or
                row['source_kind'] != 'synthetic_scene_request' or
                row['native_observed'] is not False or row['legal_verdict'] is not None):
            raise ValueError('signal/source claim differs')
        if (row['marked_stop_line_x_m'], row['near_side_crosswalk_x_m'],
                row['intersection_entry_x_m']) != (-12, -9, -6):
            raise ValueError('stop-point hierarchy differs')
        if row['ego_front_x_m'] != round(row['ego_center_xy_m'][0] + 2, 6):
            raise ValueError('front-body geometry differs')
        expected_ego = (-35 + .2 * min(i, 100) + .2 * max(0, i - 210)
                        if cfg['case_suffix'] == 'controlled_1' else -35 + .2 * i)
        if (row['ego_center_xy_m'] != [round(min(35, expected_ego), 6), -1.75] or
                row['other_center_xy_m'] != [1.75, round(min(35, -35 + .2 * i), 6)]):
            raise ValueError('controlled route or other-vehicle request differs')
        positions.append(row['ego_center_xy_m'][0])
    if cfg['case_suffix'] == 'controlled_1':
        if positions[100:211] != [-15.0] * 111 or rows[210]['ego_front_x_m'] >= -12:
            raise ValueError('requested complete stop before line differs')
    elif cfg['case_suffix'] == 'controlled_2':
        if any(b <= a for a, b in zip(positions[:250], positions[1:251])):
            raise ValueError('requested no-stop traversal differs')
    else:
        raise ValueError('unknown exact case')
    return {'frames': 600, 'case_suffix': cfg['case_suffix'],
            'native_observed': False, 'legal_verdict': None}

if __name__ == '__main__':
    print(json.dumps(check()))
'''

TEST = '''import unittest
from check import check

class ExactOutageRequest(unittest.TestCase):
    def test_source_and_requested_stop(self):
        result = check()
        self.assertEqual(result['frames'], 600)
        self.assertFalse(result['native_observed'])
        self.assertIsNone(result['legal_verdict'])
'''


def build():
    if sha(SOURCE) != SOURCE_SHA:
        raise ValueError('frozen assignment hash differs')
    source = json.loads(SOURCE.read_text())
    plan = CASE / 'case-plan.json'
    if (source['law']['text'] != json.loads(plan.read_text())['source_law']['text'] or
            source['cell']['layout'] != 'intersection' or
            source['cell']['control'] != 'traffic_light'):
        raise ValueError('frozen law or cell differs')
    entries = []
    for suffix in ('controlled_1', 'controlled_2'):
        folder = HERE / 'requests' / suffix
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'request.jsonl'
        path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                for row in rows(suffix)))
        cfg = {'case_suffix': suffix, 'assignment_sha256': SOURCE_SHA,
               'plan_sha256': sha(plan), 'rows_sha256': sha(path),
               'selected': False, 'original_native_observed': False,
               'stop_line_present_requested': True,
               'official_signal_state_verified': False}
        files = [{'path': name, 'content': content} for name, content in (
            ('assignment-source.json', SOURCE.read_text()),
            ('case-plan.json', plan.read_text()),
            ('request.jsonl', path.read_text()),
            ('config.json', json.dumps(cfg, indent=2) + '\n'),
            ('check.py', CHECK), ('tests/test_exact.py', TEST))]
        construction = {'case_id': CASE.name + '__' + suffix,
                        'cell_id': 'C111331', 'law_id': 'NRS-484B-250-4',
                        'actor': 'motor_vehicle_driver', 'entrypoint': 'check.py',
                        'files': files, 'status': 'unselected_cpu_diagnostic',
                        'recording_description': 'Requested inoperative uncovered signal; no original Native confirmation.'}
        target = HERE / 'runtime-drafts' / suffix / 'construction.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(construction, indent=2) + '\n')
        entries.append({'case_id': construction['case_id'],
                        'construction': str(target.relative_to(HERE)),
                        'construction_sha256': sha(target), 'candidates': [],
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Signal failure state, stop geometry and yielding need original capture.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': CASE.name, 'status': 'draft_not_selected',
                'cases': entries, 'original_native_observed': False,
                'delivery_ready': False}
    output = HERE / 'draft-execution-manifest.json'
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases'])}))
