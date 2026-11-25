"""Materialize source-hashed unselected Native constructions for five contrasts."""

import hashlib
import json
from pathlib import Path

from native_red import CONDITIONS, plan

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


TEST = '''import json
import unittest
from pathlib import Path
from native_red import check_plan, check_map, requested_speed


class ExactNativeRed(unittest.TestCase):
    def test_exact_plan_and_route(self):
        cfg = json.loads(Path('config.json').read_text())
        self.assertEqual(check_plan(cfg)['frames'], 600)
        self.assertEqual(check_map()['roadway_y_abs_max_m'], 3.5)
        self.assertEqual(requested_speed(cfg['condition'], 0), 0)
        self.assertEqual(requested_speed(cfg['condition'], 220) > 0,
                         cfg['requested_entry'])
'''


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    entries = []
    for condition in CONDITIONS:
        case_id = plan(condition)['case_id']
        options = []
        for candidate in ('primary', 'fallback1'):
            config = plan(condition, candidate)
            config.update(selected_case_id=case_id,
                          source_packets=[], case=condition,
                          recording_description='Pedestrian highway-entry contrast under surveyed steady red and other-device indication.')
            files = [{'path': name, 'content': value} for name, value in (
                ('runner.py', (HERE / 'runner.py').read_text()),
                ('native_red.py', (HERE / 'native_red.py').read_text()),
                ('source_join.py', (HERE / 'source_join.py').read_text()),
                ('finalize.py', (HERE / 'finalize.py').read_text()),
                ('road.xodr', (HERE / 'road.xodr').read_text()),
                ('config.json', json.dumps(config, indent=2) + '\n'),
                ('tests/test_native.py', TEST))]
            construction = {'case_id': case_id, 'cell_id': 'C111331',
                            'law_id': 'NRS-484B-307-8b', 'actor': 'pedestrian',
                            'entrypoint': 'runner.py', 'files': files,
                            'recording_description': config['recording_description'],
                            'status': 'unselected_native_draft',
                            'measurement_plan': 'Original walker footprint, both signal readbacks, four RGB sources and frame map.',
                            'static_checks': ['exact frozen identity', 'map signal and roadway geometry'],
                            'termination_rules': ['600 source frames at 20 Hz', 'abort on missing Native head or camera'],
                            'mechanisms': ['OpenDRIVE intersection', 'walker control', 'Native signal readback']}
            target = HERE / 'native-drafts' / condition / candidate / 'construction.json'
            write(target, construction)
            options.append({'id': candidate,
                            'construction': str(target.relative_to(HERE)),
                            'construction_sha256': sha(target)})
        entries.append({'case_id': case_id,
                        'construction': options[0]['construction'],
                        'construction_sha256': options[0]['construction_sha256'],
                        'candidates': [{**options[1],
                                        'trigger': {'source': 'native-capture-report.json',
                                                    'metric': 'walker_spawn_and_road_entry',
                                                    'failure_condition': 'spawn failed or intended highway entry absent'},
                                        'changed_knobs': ['walker_start_xy_m.y +0.8 m']}],
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Pedestrian spawn may overlap a road edge or fail to achieve intended entry.'}})
    manifest = {'format': 'worker-unselected-native-draft-manifest-v1',
                'assignment_id': ASSIGNMENT.name, 'status': 'draft_not_selected',
                'cases': entries, 'native_executed': False,
                'delivery_ready': False}
    target = HERE / 'draft-native-execution-manifest.json'
    write(target, manifest)
    print(json.dumps({'cases': len(entries), 'candidates': len(entries) * 2,
                      'manifest_sha256': sha(target)}, sort_keys=True))


if __name__ == '__main__':
    main()
