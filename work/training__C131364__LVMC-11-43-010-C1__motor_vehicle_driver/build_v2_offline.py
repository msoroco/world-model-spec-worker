"""Pin the two 600-frame roundabout requests to current v2 offline bundles."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / 'native'
OUT = HERE / 'v2-diagnostic'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pose(witness, frame):
    radius = 23.75 if witness == 'witness_1' else 27.25
    lane = -1 if witness == 'witness_1' else -2
    time_s = (frame + 1) / 20
    arc = radius * math.pi / 2
    distance = min(6 * time_s, 30 + arc + 20)
    if distance < 30:
        phase, road, x, y, heading = 'entry', 10, -30 + distance, -radius, 0
    elif distance < 30 + arc:
        theta = -math.pi / 2 + (distance - 30) / radius
        phase, road = 'circulation', 11
        x, y, heading = radius * math.cos(theta), radius * math.sin(theta), math.degrees(theta + math.pi / 2)
    else:
        phase, road, x, y, heading = 'exit', 12, radius, distance - 30 - arc, 90
    return {'frame': frame, 'time_s': time_s, 'source_kind': 'authored_native_request',
            'witness': witness, 'candidate_id': 'primary', 'road_id': road,
            'lane_id': lane, 'phase': phase, 'ego_x_m': round(x, 6),
            'ego_y_m': round(y, 6), 'ego_heading_deg': round(heading, 6),
            'actual_exit_observed': False, 'roundabout_verified': False}


def main():
    recording = {'channels': [{'name': 'roundabout_route', 'unit': 'structured',
        'sampling_rate_hz': 20, 'method': 'Native actor pose and map lane readback',
        'time_window': 'full 30 s / 600-frame attempt',
        'reference_frame': 'Native OpenDRIVE road and lane identities',
        'uncertainty': 'Physical roundabout, actual exit and lane occupancy require original capture'}],
        'context_inputs': [], 'limitations': ['Authored route is not original Native observation']}
    cases = []
    for witness in ('witness_1', 'witness_2'):
        case_id = HERE.name + '__' + witness
        folder = OUT / witness
        folder.mkdir(parents=True, exist_ok=True)
        track = folder / 'source-track.jsonl'
        track.write_text(''.join(json.dumps(pose(witness, i), separators=(',', ':')) + '\n'
                                 for i in range(600)))
        road = NATIVE / 'left-exit-road.xodr'
        assignment = ROOT / 'inputs' / HERE.name / 'assignment.json'
        plan = HERE / 'case-plan.json'
        config = {'case_id': case_id, 'selected_case_id': case_id,
            'case': {'case_id': case_id}, 'cell_id': 'C131364',
            'law_id': 'LVMC-11-43-010-C1', 'actor': 'motor_vehicle_driver',
            'duration_s': 30, 'rate_hz': 20,
            'cameras': [{'name': name, 'width': width, 'height': height}
                for name, width, height in (('overview', 1920, 1080),
                    ('approach', 1280, 720), ('reference_corner', 1280, 720),
                    ('driver_reference', 1280, 720))],
            'required_atoms': ['ru.motor_vehicle', 'kin.position', 'kin.heading'],
            'source_packets': [], 'recording_description': recording,
            'assignment_sha256': sha(assignment), 'case_plan_sha256': sha(plan),
            'road_sha256': sha(road), 'track_sha256': sha(track)}
        files = [{'path': name, 'content': source.read_text()}
            for name, source in [('v2_runner.py', NATIVE / 'v2_runner.py'),
                ('source-track.jsonl', track), ('road.xodr', road),
                ('assignment-source.json', assignment), ('case-plan.json', plan)]]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        test = '''import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from v2_runner import check

class Route(unittest.TestCase):
    def test_600_source_bound_route(self):
        result = check(Path.cwd())
        self.assertEqual(result['checked_frames'], 600)
        self.assertFalse(result['actual_exit_observed'])

    def copy(self):
        temporary = tempfile.TemporaryDirectory()
        root = Path(temporary.name)
        for name in ('config.json', 'source-track.jsonl', 'road.xodr',
                     'assignment-source.json', 'case-plan.json'):
            shutil.copy2(name, root / name)
        return temporary, root

    def test_changed_track_hash_rejected(self):
        temporary, root = self.copy()
        with temporary:
            (root / 'source-track.jsonl').write_text((root / 'source-track.jsonl').read_text() + '\\n')
            with self.assertRaisesRegex(ValueError, 'source hash differs'):
                check(root)

    def test_changed_assignment_rejected(self):
        temporary, root = self.copy()
        with temporary:
            (root / 'assignment-source.json').write_text('{}\\n')
            with self.assertRaisesRegex(ValueError, 'Frozen assignment source differs'):
                check(root)

    def test_rebound_route_change_rejected(self):
        temporary, root = self.copy()
        with temporary:
            path = root / 'source-track.jsonl'
            lines = path.read_text().splitlines()
            item = json.loads(lines[300]); item['lane_id'] = -99
            lines[300] = json.dumps(item)
            path.write_text('\\n'.join(lines) + '\\n')
            config = json.loads((root / 'config.json').read_text())
            config['track_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            (root / 'config.json').write_text(json.dumps(config) + '\\n')
            with self.assertRaisesRegex(ValueError, 'route source differs'):
                check(root)
'''
        files.append({'path': 'tests/test_route.py', 'content': test})
        construction = {'actor': 'motor_vehicle_driver', 'case_id': case_id,
            'cell_id': 'C131364', 'law_id': 'LVMC-11-43-010-C1',
            'entrypoint': 'v2_runner.py', 'files': files,
            'recording_description': recording,
            'status': 'unselected_current_v2_cpu_diagnostic'}
        path = folder / 'construction.json'
        path.write_text(json.dumps(construction, indent=2) + '\n')
        cases.append({'case_id': case_id, 'kind': 'unselected_cpu_diagnostic',
                      'construction': str(path.relative_to(HERE)),
                      'construction_sha256': sha(path), 'candidates': []})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'unselected_current_v2_cpu_diagnostic', 'cases': cases}
    path = HERE / 'v2-offline-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(path), 'case_count': len(cases),
                      'construction_sha256': [c['construction_sha256'] for c in cases]}))


if __name__ == '__main__':
    main()
