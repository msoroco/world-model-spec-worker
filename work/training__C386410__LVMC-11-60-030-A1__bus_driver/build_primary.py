"""Bind exact two-location primary constructions to authored Native source files."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
SUFFIXES = {'designated_terminus': 'route_destination', 'undesignated_street': 'other_street'}
SOURCES = ('runner.py', 'geometry.py', 'finalize.py', 'analysis/bus_standing.py',
           'tests/test_native.py')
CHANNELS = ('ru.bus', 'st.curb_zone', 'st.transit_stop', 'dev.regulatory_sign',
            'drv.standing_or_parked', 'kin.time', 'kin.velocity', 'rel.occupies', 'st.roadway')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    entries = []
    for suffix, zone in SUFFIXES.items():
        case = AID + '__' + suffix
        description = {'channels': [{
            'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
            'method': 'Original frame-joined bus history, zone readback and source-bound context',
            'time_window': '600 original frames', 'reference_frame': 'one-way road 1 parking lane -2',
            'uncertainty': 'official designation, vehicle/operator status, actual pixels and 50 ms sampling require review'
        } for name in CHANNELS],
            'context_inputs': [{'name': 'route_designation_source', 'unit': 'structured',
                'method': 'Original referenced bytes with later independent administrative review'}],
            'limitations': ['Map marker does not prove official designation or legal standing.']}
        config = {'case_id': case, 'selected_case_id': case,
                  'supported_case_ids': [AID + '__' + item for item in SUFFIXES],
                  'candidate_id': 'primary', 'law_id': 'LVMC-11-60-030-A1',
                  'cell_id': 'C386410', 'actor': 'bus_driver', 'rate_hz': 20,
                  'duration_s': 30, 'required_atoms': [], 'source_packets': [],
                  'requested_location': zone, 'case': {'case_id': case},
                  'cameras': [{'name': name, 'width': width, 'height': height,
                    'pose_strategy': 'fixed camera placed relative to comparison target', 'fov_deg': 85}
                    for name, width, height, *_ in (
                      ('overview', 1920, 1080, 0), ('approach', 1280, 720, 0),
                      ('reference_corner', 1280, 720, 0), ('driver_reference', 1280, 720, 0))],
                  'recording_description': description,
                  'physical_completion': {'criterion': 'travel_progress',
                    'motion_source': 'trace.jsonl', 'position_key': 'position_m',
                    'minimum_progress_m': 1.0, 'engineering_tolerances_not_legal': True}}
        config_text = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
        files = [{'path': path, 'content': (ROOT / path).read_text(),
                  'source': str((ROOT / path).relative_to(REPO))} for path in SOURCES]
        files.append({'path': 'config.json', 'content': config_text})
        construction = {'case_id': case, 'law_id': config['law_id'],
            'cell_id': config['cell_id'], 'actor': config['actor'], 'entrypoint': 'runner.py',
            'files': files, 'recording_description': description,
            'measurement_plan': {'entrypoint': 'finalize.py',
                'required_sources': ['bus-history.jsonl', 'bus-context.json', 'video_frames.jsonl'],
                'designation_policy': 'unverified until independent original authority'},
            'static_checks': ['one-way road with parking lane -2',
                'two source-distinct location targets', 'four canonical cameras and 600 frames'],
            'termination_rules': ['600 original frames', 'restore world and destroy owned actors'],
            'mechanisms': ['approach then brake at source-readback zone',
                'original Native post-tick velocity and four-camera identities'],
            'status': 'selected_cpu_construction_physical_unverified'}
        path = ROOT / 'cases' / suffix / 'construction.json'
        write(path, construction)
        entry = {'case_id': case, 'kind': 'delivery',
                 'construction': str(path.relative_to(ROOT)),
                 'construction_sha256': sha(path),
                 'candidate_risk': {'status': 'physical',
                    'reason': 'Bus parking-lane spawn and brake position may fail in Native CARLA.'},
                 'candidates': [], 'delivery_readiness': 'incomplete',
                 'measurement_procedure': {'entrypoint': 'finalize.py'},
                 'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                    'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}}
        entries.append(entry)
        if suffix == 'designated_terminus':
            write(ROOT / 'config.json', config)
            write(ROOT / 'construction.json', construction)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': sha(REPO / 'runtime' / 'SOURCE-MANIFEST.json'),
                'status': 'partial', 'cases': entries}
    write(ROOT / 'execution-manifest.json', manifest)


if __name__ == '__main__':
    build()
