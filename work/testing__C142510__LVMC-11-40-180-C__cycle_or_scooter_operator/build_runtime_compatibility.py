"""Build exact synthetic-only recipes for pinned compatibility and saved checks."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
DONOR = ROOT / 'work/testing__C135087__NRS-484B-517__motor_vehicle_driver/diagnostics'
SOURCE = DONOR / 'loading_open_waiting'
NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHANNELS = [
    ('sidewalk_body_history', 'm', 'joined rider/pedestrian centers and sidewalk ID'),
    ('pedestrian_audio', 'synthetic emission event', 'emitter frame schedule, not an original waveform'),
    ('rider_response', 'm/s and brake state', 'rider speed and brake frame schedule'),
    ('camera_frame_identity', 'original frame ID', 'four synchronized camera frame identities'),
]
DESCRIPTION = {'channels': [
    {'name': name, 'unit': unit, 'method': method, 'sampling_rate_hz': 20,
     'time_window': 'all 900 frames', 'reference_frame': 'original frame/time',
     'uncertainty': 'synthetic fixture is not physical evidence'}
    for name, unit, method in CHANNELS],
    'context_inputs': [],
    'limitations': ['Original connected sidewalk, pedestrian microphone waveform, yielding and legal audibility remain unresolved.']}


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
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    witness = plan['selected_branches'][0]
    plan['requirement_dispositions'] = [{
        'requirement': witness['requirement'], 'source': witness['source'],
        'status': 'selected_required',
        'case_ids': [case['case_id'] for case in plan['cases']],
        'evidence_or_gap': 'Synthetic CPU compatibility only; original reviewed connected sidewalk and audio capture absent.',
        'reason': 'Exact connected sidewalk overtaking law; source-dependent physical and legal review remains open.'}]
    dump(plan_path, plan)
    donor = json.loads((DONOR / 'loading_open_waiting-generator.json').read_text())
    note = HERE / 'diagnostic-source-note.json'
    entries = []
    proposals = []
    for case in plan['cases']:
        cid = case['case_id']
        name = cid.removeprefix(AID + '__')
        construction_path = HERE / ('construction-diagnostic-' + name + '.json')
        construction = json.loads(construction_path.read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        config = json.loads(files['config.json'])
        config['case']['recording_description'] = DESCRIPTION
        config['cameras'] = list(NAMES)
        files['config.json'] = json.dumps(config, indent=2) + '\n'
        files['analysis.py'] = (HERE / 'analysis.py').read_text()
        construction['recording_description'] = DESCRIPTION
        construction['files'] = [{'path': path, 'content': content} for path, content in files.items()]
        compat_path = HERE / ('construction-compatibility-' + name + '.json')
        dump(compat_path, construction)
        scene = json.loads(files['scene.json'])
        folder = HERE / 'diagnostics' / name
        folder.mkdir(parents=True, exist_ok=True)
        rows = []
        for frame in range(900):
            rows.append({'frame': frame, 'time_s': frame / 20,
                         'rider_kind': scene['rider_kind'],
                         'relative_center_x_m': (frame - 300) / 50,
                         'emitted': frame == config['case']['signal_frame'],
                         'brake_applied': config['case']['rider_response'] == 'yield_brake' and 150 <= frame < 300,
                         'rider_speed_mps': 1.0 if frame < 300 else 1.5})
        rows_path = folder / 'overtake-rows.json'
        dump(rows_path, rows, compact=True)
        copied = []
        for relative in ('trace.jsonl', 'video_frames.jsonl',
                         'capture/native/frames.jsonl', 'capture/evidence.jsonl'):
            target = folder / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((SOURCE / relative).read_bytes())
            copied.append({'path': relative, 'source': str(target.relative_to(ROOT)), 'sha256': sha(target)})
        provenance = folder / 'acquisition-provenance.json'
        dump(provenance, {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                          'scope': 'source-shaped CPU software diagnostic only'})
        for path in (rows_path, note, provenance):
            copied.append({'path': path.name, 'source': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        generator = copy.deepcopy(donor)
        generator['files']['capture/manifest.json'] = json.dumps({
            'acquisition': 'synthetic_fixture', 'case_id': cid,
            'extraction_confirmed': True, 'frames': 900,
            'observation_contract_version': 2, 'required_observations': [],
            'complete_driving_lanes': True,
            'native_map_facts': {'path': 'native_map_facts.json',
                                 'sha256': hashlib.sha256(generator['files']['capture/native_map_facts.json'].encode()).hexdigest()},
            'sources': {'road.xodr': hashlib.sha256(generator['files']['road.xodr'].encode()).hexdigest(),
                        'trace.jsonl': sha(folder / 'trace.jsonl')}}, indent=2) + '\n'
        generator_path = HERE / 'diagnostics' / (name + '-generator.json')
        dump(generator_path, generator, compact=True)
        recipe_path = HERE / 'diagnostics' / (name + '-recipe.json')
        dump(recipe_path, {'format': 'worker-fixture-recipe', 'sources': copied,
                           'generator': {'source': str(generator_path.relative_to(ROOT)),
                                         'sha256': sha(generator_path)}})
        contract_path = HERE / 'diagnostics' / (name + '-measurement-contract.json')
        dump(contract_path, {'format': 'worker-measurement-contract', 'case_id': cid,
                             'requirements': [{'disposition_index': 0,
                                               'requirement': witness['requirement'],
                                               'source': witness['source'],
                                               'output_key': 'sidewalk_overtake_signal',
                                               'method': 'measure_overtake', 'value_type': 'object',
                                               'kind': 'measured',
                                               'inputs': ['overtake-rows.json', 'diagnostic-source-note.json']}],
                             'negative': {'remove': ['overtake-rows.json'],
                                          'error_contains': 'Missing required source: overtake-rows.json'}})
        entries.append({'case_id': cid, 'kind': 'capability_research',
                        'construction': compat_path.name,
                        'construction_sha256': sha(compat_path),
                        'fixture_recipe': str(recipe_path.relative_to(ROOT)),
                        'measurement_contract': str(contract_path.relative_to(HERE)),
                        'measurement_procedure': {'entrypoint': 'analysis.py'}})
        proposals.append({'case_id': cid, 'target_law_id': 'LVMC-11-40-180-C',
                          'target_type': 'connected_sidewalk_pedestrian_overtake',
                          'status': 'draft', 'rationale': 'Exact synthetic CPU probe; original sidewalk and audibility review pending.',
                          'variable_assignments': {'rider_kind': case['rider_kind'],
                                                   'signal_frame': config['case']['signal_frame'],
                                                   'rider_response': config['case']['rider_response']},
                          'unresolved_judgment_calls': ['yield right-of-way', 'audible to pedestrian'],
                          'recording_description': DESCRIPTION})
    dump(HERE / 'proposals/cases.json', {'cell_id': 'C142510',
                                        'actor': 'cycle_or_scooter_operator',
                                        'status': 'draft', 'sweep_specs': [], 'cases': proposals})
    dump(HERE / 'execution-manifest.compatibility-diagnostic.json',
         {'format': 'worker-execution-manifest', 'assignment_id': AID,
          'status': 'synthetic_compatibility_only',
          'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
          'cases': entries})
    return len(entries)


if __name__ == '__main__':
    print('synthetic compatibility recipes:', build())
