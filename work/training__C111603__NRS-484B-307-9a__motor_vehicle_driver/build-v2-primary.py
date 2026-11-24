"""Bind the existing witness_1 Native construction to a current v2 CPU draft."""
import hashlib
import json
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / 'native'
OUT = HERE / 'v2-primary/witness_1'
CASE = HERE.name + '__witness_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def main():
    draft = json.loads((NATIVE / 'runtime-drafts/witness_1/primary/construction.json').read_text())
    bundle = NATIVE / 'drafts/witness_1/primary'
    construction = dict(draft)
    construction['files'] = [dict(item) for item in draft['files']]
    for item in construction['files']:
        if item['path'] == 'work/' + HERE.name + '/native/capture.py':
            item['content'] = (NATIVE / 'capture.py').read_text()
    construction['files'].append({'path': 'work/' + HERE.name + '/native/signal_heads.py',
        'content': (NATIVE / 'signal_heads.py').read_text()})
    construction['files'].append({'path': 'tests/test_signal_heads.py',
        'content': '''import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "work" / "ASSIGNMENT" / "native"))
from signal_heads import resolve, sample

class Actor:
    type_id = "traffic.traffic_light"
    def __init__(self, actor_id, source_id, state):
        self.id, self.source_id, self.state = actor_id, source_id, state
    def get_opendrive_id(self):
        return self.source_id
    def get_state(self):
        return self.state

class SignalIdentity(unittest.TestCase):
    def test_distinct_authored_heads(self):
        red = Actor(1, "601", "Red")
        arrow = Actor(2, "1603", "Green")
        self.assertEqual(sample(*resolve([arrow, red]))["arrow"]["opendrive_id"], "1603")
        with self.assertRaises(ValueError):
            resolve([red])
        with self.assertRaises(ValueError):
            resolve([red, red, arrow])
        with self.assertRaises(ValueError):
            sample(red, Actor(2, "1603", "Yellow"))
'''.replace('ASSIGNMENT', HERE.name)})
    construction['files'].append({'path': 'road.xodr',
        'content': (bundle / 'arrow-intersection.xodr').read_text()})
    recording = {'channels': [{'name': 'native_actor_signal_samples',
        'unit': 'structured', 'sampling_rate_hz': 20,
        'method': 'original Native actor and OpenDRIVE signal-head readback',
        'time_window': 'full 30 s / 600-frame attempt',
        'reference_frame': 'Native actor, map and camera-frame identities',
        'uncertainty': 'Directional-arrow pixels, governance and lawful use require independent review'}],
        'context_inputs': [], 'limitations': ['CPU source-shape draft has no physical Native pixels or legal verdict']}
    config = {'case_id': CASE, 'selected_case_id': CASE,
        'case': {'case_id': CASE}, 'cell_id': 'C111603',
        'law_id': 'NRS-484B-307-9a', 'actor': 'motor_vehicle_driver',
        'duration_s': 30, 'rate_hz': 20,
        'cameras': [{'name': name, 'width': width, 'height': height}
            for name, width, height in (('overview', 1920, 1080),
              ('approach', 1280, 720), ('reference_corner', 1280, 720),
              ('driver_reference', 1280, 720))],
        'required_atoms': ['ru.motor_vehicle', 'kin.position', 'kin.heading'],
        'source_packets': [], 'recording_description': recording}
    construction['files'].append({'path': 'config.json',
                                  'content': json.dumps(config, indent=2) + '\n'})
    construction['files'].append({'path': 'finalize.py',
        'content': (NATIVE / 'finalize_v2.py').read_text()})
    construction['recording_description'] = recording
    construction['status'] = 'unselected_current_v2_cpu_diagnostic'
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'construction.json'
    path.write_text(json.dumps(construction, indent=2) + '\n')
    scratch = ROOT / '.runtime-work/c111603-v2/fixture-source'
    scratch.mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(NATIVE))
    from prove_original_processing import fixture
    fixture(bundle, scratch)
    native = [json.loads(line) for line in (scratch / 'native-raw-actors.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (scratch / 'video_frames.jsonl').read_text().splitlines()]
    assert len(native) == len(mapping) == 600
    trace, evidence, graph_rows, graphs = [], [], [], []
    for row, frame in zip(native, mapping):
        number = row['native_frame']
        frame['carla_frame'] = number
        time_s = row['time_s']
        ego = row['ego']
        other = row['other_vehicle']
        centre = ego['center_native_xyz_m']
        speed = ego['speed_mps']
        trace.append({'frame': number, 'time_s': time_s,
            'position': dict(zip(('x', 'y', 'z'), centre)), 'position_m': centre,
            'heading_deg': ego['yaw_deg'], 'speed_mps': speed,
            'velocity_mps': [speed * math.cos(math.radians(ego['yaw_deg'])),
                             speed * math.sin(math.radians(ego['yaw_deg'])), 0.0],
            'speed_mph': speed / .44704, 'speed_provenance': 'synthetic_native_sample',
            'control': {'throttle': 0, 'brake': 0}})
        evidence.append({'original_frame': number, 'recording_time_s': time_s,
            'replay_frame': number, 'replay_simulation_time_s': time_s,
            'actor_id': ego['actor_id'],
            'ego': {'position_m': centre, 'heading_deg': ego['yaw_deg'],
                'speed_mps': speed, 'speed_provenance': 'synthetic_native_sample',
                'body_vertices_m': ego['body_native_xyz_m']},
            'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                'wetness': 0, 'fog_density': 0}}})
        graph_path = f'capture/native/graphs/base/{number:08d}.adapter.json'
        graph_rows.append({'frame': number, 'simulation_time': time_s,
            'adapter_graph': f'graphs/base/{number:08d}.adapter.json',
            'base': f'graphs/base/{number:08d}.adapter.json', 'nodes': 2, 'edges': 0})
        nodes = []
        for label, actor in (('ego', ego), ('other', other)):
            point = actor['center_native_xyz_m']
            nodes.append({'id': label, 'attributes': {'sem_class': 'car',
                'entity_id': actor['actor_id'], 'vertex': point,
                'forward': [1, 0, 0], 'threedbbox': actor['body_native_xyz_m']}})
        graphs.append({'path': graph_path, 'attributes': {'frame': number,
            'simulation_time_s': time_s, 'synthetic_diagnostic': True},
            'nodes': nodes, 'edges': []})
    sources = OUT / 'sources'
    write_rows(sources / 'native-raw-actors.jsonl', native)
    write_rows(sources / 'video_frames.jsonl', mapping)
    write_rows(sources / 'trace.jsonl', trace)
    write_rows(sources / 'capture/evidence.jsonl', evidence)
    write_rows(sources / 'capture/native/frames.jsonl', graph_rows)
    for name in ('native-map-readback.json', 'native-capture-report.json'):
        (sources / name).write_bytes((scratch / name).read_bytes())
    (sources / 'capture/recorder_info.txt').write_text(
        'Create 99: vehicle.tesla.model3\nCreate 100: vehicle.tesla.model3\n')
    (sources / 'capture/manifest.json').write_text(json.dumps({
        'extraction_confirmed': True, 'frames': 600,
        'sources': {'road.xodr': sha(bundle / 'arrow-intersection.xodr'),
                    'trace.jsonl': sha(sources / 'trace.jsonl')},
        'synthetic_diagnostic': True}) + '\n')
    generator = OUT / 'generator.json'
    generator.write_text(json.dumps({'files': {}, 'graphs': graphs,
        'videos': [{'path': name + '.mkv', 'frames': 600,
            'width': width, 'height': height, 'fps': 20, 'color': 'black'}
            for name, width, height in (('overview', 1920, 1080),
                ('approach', 1280, 720), ('reference_corner', 1280, 720),
                ('driver_reference', 1280, 720))]}, separators=(',', ':')) + '\n')
    source_items = []
    for item in sorted(sources.rglob('*')):
        if item.is_file():
            assert item.stat().st_size <= 2 * 1024 * 1024
            source_items.append({'path': str(item.relative_to(sources)),
                'source': str(item.relative_to(ROOT)), 'sha256': sha(item)})
    recipe = OUT / 'recipe.json'
    recipe.write_text(json.dumps({'format': 'worker-fixture-recipe',
        'sources': source_items, 'generator': {'source': str(generator.relative_to(ROOT)),
            'sha256': sha(generator)}}, indent=2) + '\n')
    contract = OUT / 'measurement-contract.json'
    contract.write_text(json.dumps({'format': 'worker-measurement-contract',
        'case_id': CASE, 'requirements': [{'disposition_index': 0,
            'requirement': 'NRS-484B-307-9a', 'source': 'NRS 484B.307(9)(a)',
            'output_key': 'arrow_movement', 'method': 'measure', 'value_type': 'object',
            'kind': 'measured', 'inputs': ['native-raw-actors.jsonl', 'video_frames.jsonl']}],
        'negative': {'remove': ['native-raw-actors.jsonl'],
            'error_contains': 'Missing required source: native-raw-actors.jsonl'}}, indent=2) + '\n')
    cases = HERE / 'proposals/cases.json'
    cases.parent.mkdir(exist_ok=True)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    cases.write_text(json.dumps({'cases': plan['cases']}, indent=2) + '\n')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'status': 'unselected_current_v2_cpu_primary_draft',
        'cases': [{'case_id': CASE, 'kind': 'unselected_cpu_diagnostic',
                   'construction': str(path.relative_to(HERE)),
                   'construction_sha256': sha(path), 'candidates': [],
                   'measurement_contract': str(contract.relative_to(HERE)),
                   'measurement_procedure': {'entrypoint': 'finalize.py',
                       'output_schema': 'c111603-saved-analysis-v2'},
                   'fixture_recipe': str(recipe.relative_to(ROOT))}]}
    manifest_path = HERE / 'v2-primary-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'construction_sha256': sha(path),
                      'recipe_sha256': sha(recipe), 'generator_sha256': sha(generator),
                      'sources': len(source_items), 'files': len(construction['files'])}))


if __name__ == '__main__':
    main()
