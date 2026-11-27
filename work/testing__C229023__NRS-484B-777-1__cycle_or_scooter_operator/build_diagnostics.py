"""Build eight exact source-shaped, explicitly synthetic compatibility inputs."""

import copy
import hashlib
import json
from pathlib import Path

from rightside import CASES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
DONOR = ROOT / 'work/testing__C229023__NRS-484B-270-7b__cycle_or_scooter_operator/diagnostics'
SOURCE = DONOR / 'bicycle_wider_pass'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned diagnostic exceeds 2 MiB: ' + str(path))


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest_path = HERE / 'execution-manifest.draft.json'
    manifest = json.loads(manifest_path.read_text())
    donor = json.loads((DONOR / 'bicycle_wider_pass-generator.json').read_text())
    for index, case in enumerate(CASES):
        case_id = AID + '__' + case.name
        folder = HERE / 'diagnostics' / case.name
        folder.mkdir(parents=True, exist_ok=True)
        rows = []
        for frame in range(900):
            other_speed = 0. if case.target_motion == 'standing' else 2.
            relative = -10 + (frame * .04 if case.target_motion == 'standing' else frame * .02)
            rows.append({
                'frame': frame, 'time_s': frame / 20,
                'cycle_kind': case.cycle_kind, 'target_motion': case.target_motion,
                'right_impediment': case.right_impediment, 'narrow_lane': case.narrow_lane,
                'right_edge_distance_m': case.lateral_target_m,
                'relative_station_m': relative,
                'surface_clearance_m': .25, 'cycle_speed_mps': 2.8,
                'other_vehicle_speed_mps': other_speed,
                'right_access_width_m': .5 if case.right_impediment != 'none' else 1.5,
            })
        row_path = folder / 'rightside-rows.json'
        write(row_path, rows, compact=True)
        marker_path = folder / 'diagnostic-source-note.json'
        write(marker_path, {
            'format': 'c229023-7771-diagnostic-source-v1',
            'source_kind': 'synthetic_diagnostic_fixture',
            'accepted_original_source': False, 'physical_acceptance': False,
            'case_id': case_id, 'road_geometry_source_sha256': 'a' * 64,
            'lawful_speed_basis_source_sha256': 'b' * 64,
        })
        copied = []
        for name in ('trace.jsonl', 'video_frames.jsonl',
                     'capture/native/frames.jsonl', 'capture/evidence.jsonl'):
            target = folder / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / name).read_bytes())
            copied.append({'path': name, 'source': str(target.relative_to(ROOT)),
                           'sha256': sha(target)})
        provenance = folder / 'acquisition-provenance.json'
        write(provenance, {'provenance_kind': 'synthetic_fixture',
                           'diagnostic_fixture': True,
                           'scope': 'source-shaped CPU software diagnostic only',
                           'case_id': case_id,
                           'right_side_semantics_source': 'rightside-rows.json'})
        for path in (row_path, marker_path, provenance):
            copied.append({'path': path.name, 'source': str(path.relative_to(ROOT)),
                           'sha256': sha(path)})
        generator = copy.deepcopy(donor)
        generator['files']['capture/manifest.json'] = json.dumps({
            'acquisition': 'synthetic_fixture', 'case_id': case_id,
            'extraction_confirmed': True, 'frames': 900,
            'observation_contract_version': 2, 'required_observations': [],
            'complete_driving_lanes': True,
            'native_map_facts': {'path': 'native_map_facts.json',
                                 'sha256': hashlib.sha256(generator['files'][
                                     'capture/native_map_facts.json'].encode()).hexdigest()},
            'sources': {'road.xodr': hashlib.sha256(generator['files']['road.xodr'].encode()).hexdigest(),
                        'trace.jsonl': sha(folder / 'trace.jsonl')}}, indent=2) + '\n'
        generator_path = HERE / 'diagnostics' / (case.name + '-generator.json')
        write(generator_path, generator, compact=True)
        recipe_path = HERE / 'diagnostics' / (case.name + '-recipe.json')
        write(recipe_path, {'format': 'worker-fixture-recipe', 'sources': copied,
                            'generator': {'source': str(generator_path.relative_to(ROOT)),
                                          'sha256': sha(generator_path)}})
        inputs = ['rightside-rows.json', 'diagnostic-source-note.json',
                  'trace.jsonl', 'video_frames.jsonl']
        relevant = [i for i, disposition in enumerate(plan['requirement_dispositions'])
                    if case_id in disposition['case_ids']]
        contract_path = HERE / 'diagnostics' / (case.name + '-measurement-contract.json')
        write(contract_path, {'format': 'worker-measurement-contract',
                              'case_id': case_id,
                              'requirements': [
                                  {'disposition_index': i,
                                   'requirement': plan['requirement_dispositions'][i]['requirement'],
                                   'source': plan['requirement_dispositions'][i]['source'],
                                   'output_key': 'right_side_req_' + str(i),
                                   'method': 'measure_case', 'value_type': 'object',
                                   'kind': 'measured', 'inputs': inputs}
                                  for i in relevant],
                              'negative': {'remove': ['rightside-rows.json'],
                                           'error_contains': 'Missing required source: rightside-rows.json'}})
        entry = manifest['cases'][index]
        entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
        entry['measurement_contract'] = str(contract_path.relative_to(HERE))
        entry['acquisition'] = {
            name: {'entrypoint': 'analysis.py',
                   'method': 'source-shaped 900-frame right-side pass diagnostic',
                   'evidence': ('video_frames.jsonl' if name == 'camera_frame_identity'
                                else 'rightside-rows.json')}
            for name in ('right_edge_distance', 'relative_station', 'surface_clearance',
                         'cycle_speed', 'other_vehicle_speed', 'right_access_width',
                         'lane_width', 'left_turn_preparation', 'camera_frame_identity')}
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    write(manifest_path, manifest)
    return len(CASES)


if __name__ == '__main__':
    print('exact compatibility inputs:', build())
