"""Bind exact synthetic source recipes and contracts for night comparisons."""

from hashlib import sha256
import json
from pathlib import Path

from native_headlamp_probe import NIGHT_CASES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE = f'inputs/{ASSIGNMENT}/assignment.json'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    first_spec = json.loads((HERE / 'night-probes/night_299_upper-diagnostic-input.json').read_text())
    first_manifest = json.loads((HERE / 'night-299-execution-manifest.json').read_text())
    first_entry = first_manifest['cases'][0]
    plan = json.loads((HERE / 'case-plan.json').read_text())
    requirement = plan['requirement_dispositions'][0]['requirement']
    proposal = json.loads((HERE / 'proposals/cases.json').read_text())
    first_case = proposal['cases'][0]
    entries = [first_entry]
    cases = [first_case]
    for case_id, (gap_ft, uppermost) in NIGHT_CASES.items():
        if case_id == first_entry['case_id']:
            continue
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        spec = json.loads(json.dumps(first_spec))
        files = spec['files']
        rows = [json.loads(line) for line in files['following_footprints.jsonl'].splitlines()]
        delta = (gap_ft - 299) * .3048
        for row in rows:
            row['lead_corners_xy'] = [[x + delta, y] for x, y in row['lead_corners_xy']]
        files['following_footprints.jsonl'] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
        lamps = [json.loads(line) for line in files['headlamp_readbacks.jsonl'].splitlines()]
        for lamp in lamps:
            lamp['uppermost_distribution'] = uppermost
            lamp['low_beam_readback'] = True
        files['headlamp_readbacks.jsonl'] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in lamps)
        capture = json.loads(files['capture/manifest.json'])
        capture['case_id'] = case_id
        files['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
        provenance = json.loads(files['fixture-provenance.json'])
        provenance['case_id'] = case_id
        files['fixture-provenance.json'] = json.dumps(provenance, indent=2) + '\n'
        spec_path = HERE / 'night-probes' / f'{suffix}-diagnostic-input.json'
        spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
        source = spec_path.relative_to(ROOT).as_posix()
        digest = sha(spec_path)
        recipe_path = HERE / 'night-probes' / f'{suffix}-diagnostic-recipe.json'
        write(recipe_path, {'format': 'worker-fixture-recipe',
                            'sources': [{'path': f'{suffix}-diagnostic-input.json',
                                         'source': source, 'sha256': digest}],
                            'generator': {'source': source, 'sha256': digest}})
        contract_rel = f'night-probes/{suffix}-measurement-contract.json'
        write(HERE / contract_rel, {'format': 'worker-measurement-contract',
                                    'case_id': case_id,
                                    'requirements': [{
                                        'disposition_index': 0, 'requirement': requirement,
                                        'source': SOURCE,
                                        'output_key': 'headlamp_following_observation',
                                        'method': 'analyze', 'value_type': 'object',
                                        'kind': 'measured',
                                        'inputs': ['following_footprints.jsonl',
                                                   'headlamp_readbacks.jsonl',
                                                   'lighting_context.json',
                                                   'video_frames.jsonl', 'trace.jsonl',
                                                   'roadway_environment.jsonl']}],
                                    'negative': {
                                        'remove': ['headlamp_readbacks.jsonl'],
                                        'error_contains': 'Missing required source: headlamp_readbacks.jsonl'}})
        construction_rel = f'night-probes/{suffix}-construction.json'
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': construction_rel,
                        'construction_sha256': sha(HERE / construction_rel),
                        'measurement_contract': contract_rel,
                        'measurement_procedure': {'entrypoint': 'headlamp_finalizer.py'},
                        'fixture_recipe': recipe_path.relative_to(ROOT).as_posix(),
                        'native_handoff': first_entry['native_handoff'],
                        'candidate_risk': first_entry['candidate_risk'],
                        'candidates': [],
                        'negative': {'log': f'night-probes/{suffix}-compat-negative.log'},
                        'acquisition': first_entry['acquisition']})
        config = json.loads((HERE / 'night-probes' / f'{suffix}-config.json').read_text())
        item = json.loads(json.dumps(first_case))
        item['case_id'] = case_id
        item['target_type'] = 'boundary_probe' if gap_ft != 299 else 'controlled_comparison'
        item['variable_assignments']['requested_gap_ft']['value'] = gap_ft
        item['variable_assignments']['requested_uppermost_distribution']['value'] = uppermost
        item['recording_description'] = config['case']['recording_description']
        cases.append(item)
    manifest = {**first_manifest, 'cases': entries}
    write(HERE / 'night-execution-manifest.json', manifest)
    proposal['cases'] = cases
    write(HERE / 'proposals/cases.json', proposal)


if __name__ == '__main__':
    build()
