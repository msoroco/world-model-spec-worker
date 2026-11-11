"""Bind source-shaped daylight and shoulder diagnostics to exact cases."""

from hashlib import sha256
import json
from pathlib import Path

from native_headlamp_probe import CONTEXT_CASES


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE = f'inputs/{ASSIGNMENT}/assignment.json'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def lines(rows):
    return ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)


def build():
    original = json.loads((HERE / 'night-probes/night_299_upper-diagnostic-input.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    requirement = plan['requirement_dispositions'][0]['requirement']
    existing = json.loads((HERE / 'proposals/cases.json').read_text())
    first_case = existing['cases'][0]
    first_entry = json.loads((HERE / 'night-299-execution-manifest.json').read_text())['cases'][0]
    entries = []
    for case_id, (gap_ft, uppermost, time_applies, position) in CONTEXT_CASES.items():
        suffix = case_id.removeprefix(ASSIGNMENT + '__')
        spec = json.loads(json.dumps(original))
        files = spec['files']
        context = json.loads(files['lighting_context.json'])
        if not time_applies:
            context['lighting_time_applies'] = False
            context['time_source'] = 'authored synthetic NRS 484D.100 lighting-time premise for CPU software diagnostic; civil time unverified'
        files['lighting_context.json'] = json.dumps(context, indent=2) + '\n'
        roadway = [json.loads(line) for line in files['roadway_environment.jsonl'].splitlines()]
        for row in roadway:
            row['sun_altitude_angle_deg'] = -10 if time_applies else 45
            if position == 'shoulder':
                row['lane_id'] = 2
                row['lane_type_readback'] = 'Shoulder'
        files['roadway_environment.jsonl'] = lines(roadway)
        capture = json.loads(files['capture/manifest.json'])
        capture['case_id'] = case_id
        files['capture/manifest.json'] = json.dumps(capture, indent=2) + '\n'
        provenance = json.loads(files['fixture-provenance.json'])
        provenance['case_id'] = case_id
        provenance['scope'] = 'Synthetic software diagnostic; lane and civil-time context are authored readbacks, not physical evidence.'
        files['fixture-provenance.json'] = json.dumps(provenance, indent=2) + '\n'
        spec_path = HERE / 'context-probes' / f'{suffix}-diagnostic-input.json'
        spec_path.write_text(json.dumps(spec, separators=(',', ':')) + '\n')
        source = spec_path.relative_to(ROOT).as_posix()
        digest = sha(spec_path)
        recipe_path = HERE / 'context-probes' / f'{suffix}-diagnostic-recipe.json'
        write(recipe_path, {'format': 'worker-fixture-recipe',
                            'sources': [{'path': f'{suffix}-diagnostic-input.json',
                                         'source': source, 'sha256': digest}],
                            'generator': {'source': source, 'sha256': digest}})
        contract_rel = f'context-probes/{suffix}-measurement-contract.json'
        write(HERE / contract_rel, {'format': 'worker-measurement-contract',
                                    'case_id': case_id,
                                    'requirements': [{
                                        'disposition_index': 0,
                                        'requirement': requirement, 'source': SOURCE,
                                        'output_key': 'headlamp_following_observation',
                                        'method': 'analyze', 'value_type': 'object',
                                        'kind': 'measured',
                                        'inputs': ['following_footprints.jsonl',
                                                   'headlamp_readbacks.jsonl',
                                                   'lighting_context.json',
                                                   'video_frames.jsonl', 'trace.jsonl',
                                                   'roadway_environment.jsonl']}],
                                    'negative': {
                                        'remove': ['roadway_environment.jsonl'],
                                        'error_contains': 'Missing required source: roadway_environment.jsonl'}})
        construction_rel = f'context-probes/{suffix}-construction.json'
        entry = {'case_id': case_id, 'kind': 'delivery',
                 'construction': construction_rel,
                 'construction_sha256': sha(HERE / construction_rel),
                 'measurement_contract': contract_rel,
                 'measurement_procedure': {'entrypoint': 'headlamp_finalizer.py'},
                 'fixture_recipe': recipe_path.relative_to(ROOT).as_posix(),
                 'native_handoff': first_entry['native_handoff'],
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Civil-time or adjacent-shoulder placement may fail physical review.'},
                 'candidates': [],
                 'negative': {'log': f'context-probes/{suffix}-compat-negative.log'},
                 'acquisition': first_entry['acquisition']}
        entries.append(entry)
        config = json.loads((HERE / 'context-probes' / f'{suffix}-config.json').read_text())
        proposal = json.loads(json.dumps(first_case))
        proposal['case_id'] = case_id
        proposal['target_type'] = 'context_comparison'
        proposal['variable_assignments']['requested_gap_ft']['value'] = gap_ft
        proposal['variable_assignments']['requested_uppermost_distribution']['value'] = uppermost
        proposal['variable_assignments']['lighting_time_premise']['value'] = time_applies
        proposal['variable_assignments']['requested_roadway_position'] = {
            'kind': 'world_setup', 'value': position}
        proposal['recording_description'] = config['case']['recording_description']
        existing['cases'] = [row for row in existing['cases'] if row['case_id'] != case_id]
        existing['cases'].append(proposal)
    manifest = {'format': 'worker-execution-manifest',
                'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': entries}
    write(HERE / 'context-execution-manifest.json', manifest)
    write(HERE / 'proposals/cases.json', existing)


if __name__ == '__main__':
    build()
