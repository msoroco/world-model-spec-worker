"""Build five bounded synthetic-only source recipes for CPU compatibility."""

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
DONOR = ROOT / 'work/testing__C142510__LVMC-11-40-180-C__cycle_or_scooter_operator/diagnostics'
SOURCE = DONOR / 'bicycle_signal_before_yield'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def dump(path, value, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False,
                               separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError('returned diagnostic file exceeds 2 MiB')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    manifest_path = HERE / 'execution-manifest.draft.json'
    manifest = json.loads(manifest_path.read_text())
    marker = HERE / 'diagnostic-source-note.json'
    dump(marker, {'format': 'c229023-diagnostic-source-v1',
                  'source_kind': 'synthetic_diagnostic_fixture',
                  'accepted_original_source': False,
                  'physical_acceptance': False,
                  'case_ids': [row['case_id'] for row in plan['cases']]})
    donor = json.loads((DONOR / 'bicycle_signal_before_yield-generator.json').read_text())
    for i, case in enumerate(plan['cases']):
        cid = case['case_id']
        name = cid.removeprefix(AID + '__')
        folder = HERE / 'diagnostics' / name
        folder.mkdir(parents=True, exist_ok=True)
        rows = []
        for frame in range(900):
            relative = ((frame - 300) / 30 if case['pass_policy'] == 'complete'
                        else -10 + 9 * min(frame, 300) / 300 -
                        min(max(frame - 300, 0), 599) / 599)
            rows.append({'frame': frame, 'time_s': frame / 20,
                         'cycle_kind': case['cycle_kind'],
                         'pass_policy': case['pass_policy'],
                         'relative_station_m': relative,
                         'surface_clearance_m': case['lateral_offset_request_m'] - 1.2,
                         'closing_speed_mps': 2 if frame < 300 else 0})
        row_path = folder / 'pass-rows.json'
        dump(row_path, rows, compact=True)
        copied = []
        for relative in ('trace.jsonl', 'video_frames.jsonl',
                         'capture/native/frames.jsonl', 'capture/evidence.jsonl'):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / relative).read_bytes())
            copied.append({'path': relative,
                           'source': str(target.relative_to(ROOT)),
                           'sha256': sha(target)})
        provenance = folder / 'acquisition-provenance.json'
        dump(provenance, {'provenance_kind': 'synthetic_fixture',
                          'diagnostic_fixture': True,
                          'scope': 'source-shaped CPU software diagnostic only',
                          'case_id': cid,
                          'generic_capture_transport': True,
                          'passing_semantics_source': 'pass-rows.json'})
        for path in (row_path, marker, provenance):
            copied.append({'path': path.name,
                           'source': str(path.relative_to(ROOT)),
                           'sha256': sha(path)})
        generator = copy.deepcopy(donor)
        generator['files']['capture/manifest.json'] = json.dumps({
            'acquisition': 'synthetic_fixture', 'case_id': cid,
            'extraction_confirmed': True, 'frames': 900,
            'observation_contract_version': 2, 'required_observations': [],
            'complete_driving_lanes': True,
            'native_map_facts': {
                'path': 'native_map_facts.json',
                'sha256': hashlib.sha256(generator['files'][
                    'capture/native_map_facts.json'].encode()).hexdigest()},
            'sources': {'road.xodr': hashlib.sha256(
                generator['files']['road.xodr'].encode()).hexdigest(),
                        'trace.jsonl': sha(folder / 'trace.jsonl')}}, indent=2) + '\n'
        for video in generator['videos']:
            if video['path'] == 'reference_corner.mkv':
                video['path'] = 'alongside.mkv'
            if video['path'] == 'driver_reference.mkv':
                video['path'] = 'rear_reference.mkv'
        generator_path = HERE / 'diagnostics' / (name + '-generator.json')
        dump(generator_path, generator, compact=True)
        recipe_path = HERE / 'diagnostics' / (name + '-recipe.json')
        dump(recipe_path, {'format': 'worker-fixture-recipe',
                           'sources': copied,
                           'generator': {'source': str(generator_path.relative_to(ROOT)),
                                         'sha256': sha(generator_path)}})
        contract_path = HERE / 'diagnostics' / (name + '-measurement-contract.json')
        witness = plan['selected_branches'][0]
        dump(contract_path, {'format': 'worker-measurement-contract',
                             'case_id': cid,
                             'requirements': [{'disposition_index': 0,
                                               'requirement': witness['requirement'],
                                               'source': witness['source'],
                                               'output_key': 'cycle_motor_pass',
                                               'method': 'measure_case',
                                               'value_type': 'object',
                                               'kind': 'measured',
                                               'inputs': ['pass-rows.json',
                                                          'diagnostic-source-note.json']}],
                             'negative': {'remove': ['pass-rows.json'],
                                          'error_contains': 'Missing required source: pass-rows.json'}})
        entry = manifest['cases'][i]
        entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
        entry['measurement_contract'] = str(contract_path.relative_to(HERE))
        entry['acquisition'] = {
            item['name']: {'entrypoint': 'analysis.py',
                           'method': 'source-shaped 900-frame diagnostic join',
                           'evidence': ('video_frames.jsonl' if item['name'] ==
                                        'camera_frame_identity' else 'pass-rows.json')}
            for item in json.loads((HERE / ('config.json' if i == 0 else
                    'cases/' + name + '/config.json')).read_text())['case'][
                        'recording_description']['channels']}
    manifest['runtime_manifest_sha256'] = sha(ROOT / 'runtime/SOURCE-MANIFEST.json')
    dump(manifest_path, manifest)
    return len(manifest['cases'])


if __name__ == '__main__':
    print('compatibility inputs:', build())
