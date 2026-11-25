"""Build exact synthetic passenger-zone recipes and measurement contracts."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
DONOR = ROOT / 'work/testing__C135087__NRS-484B-517__motor_vehicle_driver/diagnostics'
SOURCE = DONOR / 'loading_open_waiting'


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
    witness = plan['selected_branches'][0]
    donor = json.loads((DONOR / 'loading_open_waiting-generator.json').read_text())
    note = HERE / 'diagnostic-source-note.json'
    entries = []
    for case in plan['cases']:
        cid = case['case_id']; name = cid.removeprefix(AID + '__')
        construction = json.loads((HERE / ('construction-diagnostic-' + name + '.json')).read_text())
        files = {item['path']: item['content'] for item in construction['files']}
        files['analysis.py'] = (HERE / 'analysis.py').read_text()
        construction['files'] = [{'path': path, 'content': content} for path, content in files.items()]
        target = HERE / ('construction-compatibility-' + name + '.json')
        dump(target, construction)
        config = json.loads(files['config.json'])
        scene = json.loads(files['scene.json'])
        folder = HERE / 'diagnostics' / name
        folder.mkdir(parents=True, exist_ok=True)
        rows = []
        for frame in range(900):
            event = None
            if config['case']['passenger_action'] == 'load':
                start = 380 if name == 'load_delayed' else 330
                event = 'boarding_started' if frame == start else ('boarding_completed' if frame == start + 20 else None)
            elif config['case']['passenger_action'] == 'unload':
                event = 'alighting_started' if frame == 330 else ('alighting_completed' if frame == 350 else None)
            rows.append({'frame': frame, 'time_s': frame / 20, 'case_id': cid,
                         'conduct': config['case']['conduct'],
                         'regulations_effective': config['case']['hours'] == 'effective',
                         'ego_id': 'ego', 'passenger_id': 'passenger',
                         'zone_source_sha256': scene['zone']['marking_source_sha256'],
                         'inside_zone': 280 <= frame < 600,
                         'speed_mps': 0.0 if 280 <= frame < 600 else 3.0,
                         'passenger_event': event})
        row_path = folder / 'zone-rows.json'
        dump(row_path, rows, compact=True)
        copied = []
        for relative in ('trace.jsonl', 'video_frames.jsonl',
                         'capture/native/frames.jsonl', 'capture/evidence.jsonl'):
            path = folder / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((SOURCE / relative).read_bytes())
            copied.append({'path': relative, 'source': str(path.relative_to(ROOT)), 'sha256': sha(path)})
        provenance = folder / 'acquisition-provenance.json'
        dump(provenance, {'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
                          'scope': 'source-shaped CPU software diagnostic only'})
        for path in (row_path, note, provenance):
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
                                               'output_key': 'passenger_curb_zone',
                                               'method': 'measure_passenger_zone', 'value_type': 'object',
                                               'kind': 'measured',
                                               'inputs': ['zone-rows.json', 'diagnostic-source-note.json']}],
                             'negative': {'remove': ['zone-rows.json'],
                                          'error_contains': 'Missing required source: zone-rows.json'}})
        entries.append({'case_id': cid, 'kind': 'capability_research',
                        'construction': target.name, 'construction_sha256': sha(target),
                        'fixture_recipe': str(recipe_path.relative_to(ROOT)),
                        'measurement_contract': str(contract_path.relative_to(HERE)),
                        'measurement_procedure': {'entrypoint': 'analysis.py'}})
    dump(HERE / 'execution-manifest.compatibility-diagnostic.json',
         {'format': 'worker-execution-manifest', 'assignment_id': AID,
          'status': 'synthetic_compatibility_only',
          'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
          'cases': entries})
    return len(entries)


if __name__ == '__main__':
    print('synthetic passenger-zone compatibility recipes:', build())
