"""Build six sealed, exact inline Native bundles for CPU materialization.

The builder has no authority to choose a physical map or certify a parcel. It
packages the same source-bound implementation with a frozen case identity.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
ASSIGNMENT = FOLDER.name
SOURCES = ('runner.py', 'native_capture.py', 'route_controller.py',
           'property_route.py', 'case_observation.py', 'map_binding.py',
           'saved_delivery.py', 'comparison_audit.py')
CAMERAS = [('overview', 1920, 1080, 'fixed whole intersection'),
           ('approach', 1280, 720, 'fixed approach signal and body path'),
           ('property', 1280, 720, 'fixed parcel connector and boundary'),
           ('destination', 1280, 720, 'fixed intersecting street entry')]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def build() -> dict:
    plan = json.loads((FOLDER / 'case-plan.json').read_text())
    cases = plan['cases']
    expected = [ASSIGNMENT + '__' + name for name in (
        'private_bypass', 'public_bypass', 'ordinary_crossing',
        'no_approach_red', 'destination_red', 'other_purpose')]
    if [case['case_id'] for case in cases] != expected:
        raise ValueError('six exact case identities or order changed')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': ASSIGNMENT,
                'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
                'cases': []}
    channels = [
        ('original vehicle class', 'actor registry', 'trace.json actor_source'),
        ('approach signal identity, facing and state', 'Native signal observer 20 Hz', 'trace.json approach_signal_history'),
        ('source parcel classification and boundaries', 'reviewed parcel authority joined to OpenDRIVE', 'map-packet.json properties'),
        ('ego body path and street entry', 'Native body transform 20 Hz', 'trace.json ego and destination_entry_frame'),
        ('destination street traffic signal', 'Native signal observer 20 Hz', 'trace.json destination_signal_history'),
        ('separate avoidance purpose', 'authored source context', 'trace.json purpose'),
        ('original four-camera frame map', 'Native synchronized camera observer 20 Hz', 'frame-map.jsonl and four PNG archives'),
    ]
    description = {'channels': [{'name': name, 'unit': 'source observation',
                                 'sampling_rate_hz': 20, 'method': method,
                                 'time_window': 'original 45-second episode',
                                 'reference_frame': 'original Native frame joined to camera map',
                                 'source': source,
                                 'uncertainty': 'Physical motion, parcel authority and pixel visibility require independent local review'}
                                for name, method, source in channels],
                   'context_inputs': [{'name': 'reviewed original map and parcel authority',
                                       'method': 'SHA-256 OpenDRIVE, authority and exact route join'}],
                   'limitations': ['Diagnostic CPU packets do not establish parcel authority or physical realization.',
                                   'Avoidance purpose is separately sourced and cannot be inferred from route shape.']}
    for case in cases:
        case_id = case['case_id']
        config = {'assignment_id': ASSIGNMENT, 'selected_case_id': case_id,
                  'law_id': plan['law_id'], 'cell_id': plan['cell_id'],
                  'actor': plan['actor'], 'rate_hz': 20, 'duration_s': 45,
                  'cameras': [{'name': name, 'width': width, 'height': height,
                               'pose_strategy': pose, 'fov_deg': 90}
                              for name, width, height, pose in CAMERAS],
                  'capture_provenance': 'original Native samples required',
                  'required_atoms': [], 'source_packets': [],
                  'supported_case_ids': expected,
                  'case': {'case_id': case_id, 'purpose': case['purpose'],
                           'recording_description': description}}
        files = [{'path': 'config.json', 'content': json.dumps(config, indent=2, sort_keys=True) + '\n'}]
        for name in SOURCES:
            files.append({'path': name, 'source': str((FOLDER / name).relative_to(ROOT)),
                          'content': (FOLDER / name).read_text()})
        files.append({'path': 'tests/test_bundle.py',
                      'source': str((FOLDER / 'bundle_test.py').relative_to(ROOT)),
                      'content': (FOLDER / 'bundle_test.py').read_text()})
        construction = {'case_id': case_id, 'cell_id': plan['cell_id'],
                        'law_id': plan['law_id'], 'actor': plan['actor'],
                        'entrypoint': 'runner.py', 'recording_description': description,
                        'files': files}
        suffix = case_id.rsplit('__', 1)[1]
        path = FOLDER / 'constructions' / (suffix + '.json')
        write(path, construction)
        manifest['cases'].append({'case_id': case_id, 'kind': 'delivery',
                                  'construction': str(path.relative_to(FOLDER)),
                                  'construction_sha256': sha(path),
                                  'fixture_recipe': str((FOLDER / 'diagnostics' / suffix / 'fixture-recipe.json').relative_to(ROOT)),
                                  'candidate_risk': case['physical_risk_assessment'],
                                  'candidates': [],
                                  'proof_status': 'inline_cpu_draft_physical_pending'})
    write(FOLDER / 'execution-manifest.draft.json', manifest)
    return {'assignment_id': ASSIGNMENT, 'case_count': len(cases),
            'manifest': 'execution-manifest.draft.json', 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
