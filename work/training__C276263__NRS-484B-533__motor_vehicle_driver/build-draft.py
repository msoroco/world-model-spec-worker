"""Package exact graded-standing reference/contrast Native CPU drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = (HERE.name + '__reference', HERE.name + '__contrast')
CONTROLS = {'reference': {'brake': True, 'steer': -.55},
            'contrast': {'brake': False, 'steer': 0.0}}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    entries = []
    for case_id in CASES:
        suffix = case_id.rsplit('__', 1)[-1]
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'assignment_id': HERE.name,
                  'supported_case_ids': list(CASES), 'candidate_id': 'primary',
                  'law_id': 'NRS-484B-533', 'cell_id': 'C276263',
                  'actor': 'motor_vehicle_driver', 'rate_hz': 20, 'duration_s': 30,
                  'cameras': ['overview', 'approach', 'reference_corner',
                              'driver_reference'],
                  'requested_controls': CONTROLS[suffix],
                  'required_saved_sources': ['vehicle-frames.jsonl', 'grade-readback.json',
                                             'occupancy-frames.jsonl', 'video_frames.jsonl',
                                             'trace.jsonl', 'instrument-frames.jsonl'],
                  'required_atoms': [], 'source_packets': [],
                  'recording_description': {'channels': [
                      {'name': 'engine_running', 'unit': 'categorical',
                       'method': 'instrumented original engine state at each frame',
                       'sampling_rate_hz': 20, 'time_window': '600 frames',
                       'reference_frame': 'original vehicle actor',
                       'uncertainty': 'instrument method and calibration require local review'},
                      {'name': 'parking_brake_set', 'unit': 'categorical',
                       'method': 'original Native control readback at each frame',
                       'sampling_rate_hz': 20, 'time_window': '600 frames',
                       'reference_frame': 'original vehicle actor',
                       'uncertainty': 'brake effectiveness requires physical review'},
                      {'name': 'front_wheel_heading_to_curb_deg', 'unit': 'deg',
                       'method': 'calibrated original wheel orientation with separate Native FL/FR readback',
                       'sampling_rate_hz': 20, 'time_window': '600 frames',
                       'reference_frame': 'measured right curb',
                       'uncertainty': 'calibration and physical orientation require local review'},
                      {'name': 'unattended_interval', 'unit': 'categorical',
                       'method': 'original occupancy and responsible-person source',
                       'sampling_rate_hz': 20, 'time_window': '600 frames',
                       'reference_frame': 'identified responsible person and vehicle cabin',
                       'uncertainty': 'attendance and purpose require local review'}],
                      'context_inputs': [],
                      'limitations': ['Capture requires an original same-frame instrument service; endpoint and physical calibration are local prerequisites',
                                      'No numeric legal definition of perceptible or effective']},
                  'status': 'partial_cpu_draft'}
        files = [{'path': name, 'content': (HERE / 'native' / name).read_text()}
                 for name in ('runner.py', 'capture.py', 'instrumentation.py', 'grade.py', 'measure.py',
                              'finalize.py',
                              'comparison.py',
                              'tests/test_measure.py', 'tests/test_finalize.py')]
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        proposal = {'case_id': case_id, 'law_id': config['law_id'],
                    'cell_id': config['cell_id'], 'actor': config['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': config['recording_description'],
                    'measurement_plan': {'entrypoint': 'finalize.py',
                                         'required_sources': config['required_saved_sources'],
                                         'source_hash_inventory_required': True,
                                         'status': 'source_bound_cpu_draft'},
                    'mechanisms': ['authored 4% graded highway and curb with Native map readback',
                                   'vehicle parking brake command/readback and speed/position trace',
                                   'four original camera FFV1 videos and frame hashes',
                                   'frame-synchronous instrument-service packets with strict actor/frame/provenance joins',
                                   'native original front-wheel angle readback kept separate from calibrated curb-relative angle'],
                    'termination_rules': ['600 original frames at 20 Hz',
                                          'restore world and destroy owned actors',
                                          'reject unavailable or stale instrumented state'],
                    'status': 'partial_native_capture_cpu_checked_instrument_service_required'}
        path = HERE / 'draft-grade' / suffix / 'primary/construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(proposal, indent=2) + '\n')
        entries.append({'case_id': case_id, 'kind': 'delivery',
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Engine, wheel and occupancy instruments must be sourced and calibrated'},
                        'candidates': [],
                        'measurement_procedure': {'entrypoint': 'finalize.py'},
                        'delivery_readiness': 'incomplete'})
    manifest = {'format': 'worker-selected-cpu-draft-manifest-v1',
                'assignment_id': HERE.name,
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'status': 'partial', 'cases': entries}
    out = HERE / 'draft-grade-manifest.json'
    out.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'cases': {e['case_id']: e['construction_sha256'] for e in entries},
                      'manifest_sha256': sha(out)}))


if __name__ == '__main__':
    main()
