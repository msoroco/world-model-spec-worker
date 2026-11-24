"""Generate source-shaped five-frame software fixtures for all exact cases."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
MODES = ('unlit', 'low_beam', 'high_beam')


def encode(value) -> str:
    return json.dumps(value, sort_keys=True, allow_nan=False) + '\n'


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def video_hashes(specs: list[dict]) -> dict[str, str]:
    scratch = ROOT / '.runtime-work' / 'c110454-owner'
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix='fixture-video-probe-') as tmp:
        directory = Path(tmp)
        hashes = {}
        for item in specs:
            target = directory / item['path']
            command = ['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error', '-n',
                '-f', 'lavfi', '-i', f"color=c={item['color']}:s={item['width']}x{item['height']}:r={item['fps']}",
                '-frames:v', str(item['frames']), '-an', '-c:v', 'ffv1', '-threads', '1',
                '-fflags', '+bitexact', '-flags:v', '+bitexact', str(target)]
            subprocess.run(command, check=True, timeout=120)
            hashes[item['path']] = sha_bytes(target.read_bytes())
        return hashes


def build_case(seed: dict, mode: str, hashes: dict[str, str], road: str) -> dict:
    files = copy.deepcopy(seed['files'])
    case_id = ASSIGNMENT + '__' + mode
    site = {'format': 'parked-headlamp-site-v1', 'case_id': case_id,
            'cell_id': 'C110454', 'actor': 'motor_vehicle_driver',
            'diagnostic_fixture': True, 'parking_source_ref': 'synthetic-parking-polygon',
            'intersection_source_ref': 'synthetic-intersection-polygon',
            'parking_polygon_xy_m': [[0, 0], [10, 0], [10, 4], [0, 4]],
            'intersection_polygon_xy_m': [[10, 0], [14, 0], [14, 4], [10, 4]],
            'map_name': 'synthetic-diagnostic', 'map_sha256': '0' * 64}
    files['site-packet.json'] = encode(site)
    roi = {'format': 'parked-headlamp-photometry-roi-v1',
           'source_kind': 'reviewed_original_camera_roi',
           'source_ref': 'synthetic-diagnostic-ROI-only',
           'camera_view': 'approach', 'dimensions': [1280, 720],
           'lamp_polygon_xy': [[5, 5], [12, 5], [12, 12], [5, 12]],
           'background_polygon_xy': [[30, 5], [37, 5], [37, 12], [30, 12]]}
    files['lamp-roi.json'] = encode(roi)
    states = [{'frame': frame, 'time_s': frame * .05, 'speed_mps': 0.0,
               'parking_brake': True, 'footprint_inside_reviewed_parking_polygon': True,
               'body_corner_inside_intersection_count': 0,
               'light_state_bits': 0 if mode == 'unlit' else 1 if mode == 'low_beam' else 2,
               'actor_id': 17} for frame in range(5)]
    files['actor-state.jsonl'] = ''.join(encode(row) for row in states)
    files['camera-frame-map.jsonl'] = ''.join(encode({
        'frame': frame, **{view + '_source_frame': frame for view in VIEWS}})
        for frame in range(5))
    trace = [json.loads(line) for line in files['trace.jsonl'].splitlines()]
    for row in trace:
        row.update(position={'x': 10.0, 'y': -1.8, 'z': 0},
                   position_m=[10.0, -1.8, 0], speed_mps=0.0,
                   speed_mph=0.0, velocity_mps=[0, 0, 0])
    files['trace.jsonl'] = ''.join(encode(row) for row in trace)
    evidence = [json.loads(line) for line in files['capture/evidence.jsonl'].splitlines()]
    first_ego = copy.deepcopy(evidence[0]['ego'])
    first_ego.update(speed_mps=0.0, position_m=[10.0, -1.8, 0])
    for row in evidence:
        row['ego'] = copy.deepcopy(first_ego)
    files['capture/evidence.jsonl'] = ''.join(encode(row) for row in evidence)
    receipt = {'format': 'parked-headlamp-native-source-v1',
               'case_id': case_id, 'requested_mode': mode, 'frame_count': 5,
               'light_masks': {'low_beam': 1, 'high_beam': 2},
               'site_source_sha256': sha_bytes(files['site-packet.json'].encode()),
               'source_hashes': {name: sha_bytes(files[name].encode()) for name in
                                 ('actor-state.jsonl', 'camera-frame-map.jsonl')},
               'original_camera_media': {view: {'path': view + '.mkv',
                   'sha256': hashes[view + '.mkv'], 'source_frame_count': 5}
                   for view in VIEWS},
               'original_camera_videos': {view: {'path': view + '.mkv',
                   'sha256': hashes[view + '.mkv'], 'source_frame_count': 5}
                   for view in VIEWS},
               'diagnostic_site': True, 'physical_acceptance_claimed': False}
    files['native-source-receipt.json'] = encode(receipt)
    capture = json.loads(files['capture/manifest.json'])
    capture.update(case_id=case_id, acquisition='synthetic_diagnostic_fixture',
                   diagnostic_fixture=True, extraction_confirmed=True)
    capture['sources']['trace.jsonl'] = sha_bytes(files['trace.jsonl'].encode())
    files['capture/manifest.json'] = encode(capture)
    files['road.xodr'] = road
    capture['sources']['road.xodr'] = sha_bytes(files['road.xodr'].encode())
    files['capture/manifest.json'] = encode(capture)
    return {'files': files, 'graphs': copy.deepcopy(seed['graphs']),
            'videos': copy.deepcopy(seed['videos'])}


def main() -> None:
    seed = json.loads((HERE / 'generic-core-scaffold.json').read_text(encoding='utf-8'))
    donor = ROOT / 'work' / 'testing__C111125__NRS-484B-307-3a__motor_vehicle_driver' / 'diagnostic-dual_clear.json'
    road = json.loads(donor.read_text(encoding='utf-8'))['files']['road.xodr']
    hashes = video_hashes(seed['videos'])
    note = HERE / 'diagnostic-fixture-note.txt'
    note.write_text('Synthetic five-frame parked-headlamp software fixture; no physical or legal acceptance.\n',
                    encoding='utf-8')
    manifest_path = HERE / 'execution-manifest.draft.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    dispositions = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))[
        'requirement_dispositions']
    for entry, mode in zip(manifest['cases'], MODES):
        spec_path = HERE / ('diagnostic-' + mode + '.json')
        spec_path.write_text(encode(build_case(seed, mode, hashes, road)), encoding='utf-8')
        recipe_path = HERE / ('fixture-recipe-' + mode + '.json')
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': note.name,
                               'source': str(note.relative_to(ROOT)),
                               'sha256': sha_bytes(note.read_bytes())}],
                  'generator': {'source': str(spec_path.relative_to(ROOT)),
                                'sha256': sha_bytes(spec_path.read_bytes())}}
        recipe_path.write_text(encode(recipe), encoding='utf-8')
        entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
        entry['measurement_procedure'] = {'entrypoint': 'analysis.py'}
        entry['measurement_contract'] = 'measurement-contract-' + mode + '.json'
        requirements = [{
            'disposition_index': 0, 'requirement': dispositions[0]['requirement'],
            'source': dispositions[0]['source'], 'output_key': 'parked_vehicle_observation',
            'method': 'measure_parked_vehicle', 'value_type': 'object', 'kind': 'measured',
            'inputs': ['site-packet.json', 'native-source-receipt.json',
                       'actor-state.jsonl', 'camera-frame-map.jsonl'],
        }]
        if mode != 'unlit':
            requirements.extend([{
                'disposition_index': index, 'requirement': dispositions[index]['requirement'],
                'source': dispositions[index]['source'],
                'output_key': key, 'method': method,
                'value_type': 'object', 'kind': 'measured', 'inputs': inputs,
            } for index, key, method, inputs in [
                (1, 'lighted_headlamp_observation', 'measure_lighted_headlamps',
                 ['native-source-receipt.json', 'actor-state.jsonl',
                  'camera-frame-map.jsonl', 'lamp-roi.json', 'approach.mkv']),
                (2, 'depression_or_dimming_observation', 'measure_depressed_or_dimmed',
                 ['lamp-roi.json', 'approach.mkv', 'camera-frame-map.jsonl']),
            ]])
        negative_source = 'site-packet.json' if mode == 'unlit' else 'lamp-roi.json'
        (HERE / entry['measurement_contract']).write_text(encode({
            'format': 'worker-measurement-contract', 'case_id': entry['case_id'],
            'requirements': requirements,
            'negative': {'remove': [negative_source],
                         'error_contains': 'Missing required source: ' + negative_source}}),
            encoding='utf-8')
        entry['acquisition'] = {name: {'entrypoint': 'native_publication.py',
                                      'method': 'source-joined original Native/Core frame projection',
                                      'evidence': name + '.jsonl'}
                                for name in ('original_actor_state',
                                             'original_four_view_frame_map',
                                             'headlamp_emission_and_aim_review')}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('built', len(MODES), 'synthetic source-shaped parked-headlamp recipes')


if __name__ == '__main__':
    main()
