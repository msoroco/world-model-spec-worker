"""Source-shaped CPU checks for the three directed-officer draft bundles."""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / '.runtime-work'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(call):
    try:
        call()
    except ValueError:
        return True
    return False


def main():
    rows = []
    for candidate, gap in (('primary', -20), ('fallback1', -25), ('fallback2', -20)):
        bundle = SCRATCH / ('c404492-officer-offline-' + candidate + '-v5')
        if not (bundle / 'offline.log').is_file() or 'OK' not in (bundle / 'offline.log').read_text():
            raise ValueError('Pinned offline proof missing: ' + candidate)
        sys.path.insert(0, str(bundle))
        try:
            spec = importlib.util.spec_from_file_location('officer_' + candidate, bundle / 'runner.py')
            runner = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(runner)
            cfg = runner.config()
            if cfg['engineering_initial_ego_gap_m'] != gap:
                raise ValueError('Candidate gap differs')
            survey = {
                'map_name': 'reviewed-test-map', 'map_source': 'source:map',
                'lane_boundaries_source': 'source:lanes',
                'emergency_authorization_source': 'source:authorization',
                'qualifying_flash_equipment_source': 'source:equipment',
                'officer_direction_review_source': 'source:officer-review',
                'ego_blueprint': 'vehicle.ego', 'emergency_blueprint': 'vehicle.emergency',
                'ego_spawn_xyz_m': [gap, 0, 0], 'emergency_spawn_xyz_m': [0, 3.5, 0],
                'travel_heading_deg': 0,
                'camera_world_transforms': {name: {'xyz_m': [0, 0, 3],
                    'rotation_deg': [0, 0, 0]} for name in runner.CAMERAS},
                'emergency_vehicle_authorized': True,
                'qualifying_flash_equipment_reviewed': True,
                'officer_directed_otherwise': True,
                'officer_instruction_source': 'source:instruction',
                'officer_identity_source': 'source:identity',
                'officer_instruction_text': 'source:text',
                'officer_instruction_recipient': 'source:recipient',
                'officer_instruction_timing_source': 'source:timing',
                'officer_instruction_reviewer': 'source:reviewer',
            }
            runner.survey_check(survey)
            negatives = [
                rejected(lambda: runner.survey_check({**survey, 'officer_directed_otherwise': False})),
                rejected(lambda: runner.survey_check({**survey, 'officer_instruction_source': ''})),
                rejected(lambda: runner.survey_check({**survey, 'officer_instruction_reviewer': 'synthetic-fixture:r'})),
                rejected(lambda: runner.survey_check({**survey, 'emergency_vehicle_authorized': False})),
            ]
            if negatives != [True] * len(negatives):
                raise ValueError('Directed-officer negative escaped')
            finalizer_spec = importlib.util.spec_from_file_location(
                'officer_finalize_' + candidate, bundle / 'finalize.py')
            finalizer = importlib.util.module_from_spec(finalizer_spec)
            finalizer_spec.loader.exec_module(finalizer)
            with tempfile.TemporaryDirectory(prefix='c404492-officer-', dir=SCRATCH) as temp:
                source = Path(temp) / 'emergency_context.json'
                context = {'case_id': runner.CASE,
                           'review_kind': 'original_source_review',
                           'officer_directed_otherwise': True,
                           'officer_instruction_sources': {
                               key: survey[key] for key in (
                                   'officer_instruction_source', 'officer_identity_source',
                                   'officer_instruction_text', 'officer_instruction_recipient',
                                   'officer_instruction_timing_source',
                                   'officer_instruction_reviewer')}}
                source.write_text(json.dumps(context) + '\n')
                finalizer.check_context(temp, runner.CASE, False)
                context['officer_instruction_sources']['officer_instruction_source'] = ''
                source.write_text(json.dumps(context) + '\n')
                if not rejected(lambda: finalizer.check_context(temp, runner.CASE, False)):
                    raise ValueError('Missing original officer instruction accepted')
            rows.append({'candidate_id': candidate,
                         'construction_sha256': sha(HERE / 'draft-officer' / candidate / 'construction.json'),
                         'offline_passed': True, 'survey_positive': True,
                         'survey_negatives_rejected': len(negatives),
                         'finalizer_original_source_negative_rejected': True,
                         'simulation_started': False})
        finally:
            sys.path.remove(str(bundle))
            sys.modules.pop('base_runner', None)
    proof = {'format': 'c404492-officer-draft-cpu-proof-v1',
             'manifest_sha256': sha(HERE / 'draft-officer-manifest.json'),
             'rows': rows, 'physical_acceptance_claimed': False,
             'legal_verdict_claimed': False}
    path = HERE / 'current-officer-draft-proof.json'
    path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(path), 'rows': len(rows)}, sort_keys=True))


if __name__ == '__main__':
    main()
