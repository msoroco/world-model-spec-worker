"""Build lamp-on/off paired primary Native drafts; readiness stays partial."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ASSIGNMENT = HERE.name
CASES = (('controlled_1', True), ('controlled_2', False))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    batch = json.loads((ROOT/'batch.json').read_text())
    entries = []
    for suffix, lamp_on in CASES:
        case = ASSIGNMENT+'__'+suffix
        config = {
            'case_id': case, 'selected_case_id': case, 'supported_case_ids': [case],
            'candidate_id': 'primary', 'law_id': 'NRS-484D-100-1', 'cell_id': 'C179824',
            'actor': 'motor_vehicle_driver', 'lamp_setting_on': lamp_on,
            'rate_hz': 20, 'duration_s': 30, 'required_atoms': [], 'source_packets': [],
            'case': {'case_id': case},
            'cameras': [{'name': name, 'width': 1280, 'height': 720} for name in
                        ('overview', 'device_approach', 'device_face', 'vehicle_lamps')],
            'recording_description': {'channels': [
                {'name': 'native_lamp_setting', 'unit': 'boolean', 'sampling_rate_hz': 20,
                 'method': 'original CARLA VehicleLightState readback',
                 'time_window': '600 frames', 'reference_frame': 'governed roadway',
                 'uncertainty': 'actual emitted light and class sufficiency unverified'},
                {'name': 'device_and_highway_context', 'unit': 'structured', 'sampling_rate_hz': 20,
                 'method': 'OpenDRIVE sign/lane readback plus independently sourced authority',
                 'time_window': '600 frames', 'reference_frame': 'signed paved road',
                 'uncertainty': 'official status and actual pixels unverified'}],
                 'limitations': ['Class-specific chapter 484D lamp requirements not yet supplied',
                                 'Civil time and 1000-foot visibility branches remain separate',
                                 'Parked vehicle exceptions unresolved']},
            'status': 'partial_cpu_draft',
        }
        files = [{'path': name, 'content': (HERE/'native'/name).read_text()}
                 for name in ('runner.py','geometry.py','tests/test_native.py')]
        files.append({'path': 'lamp_saved_measure.py', 'content': (HERE/'lamp_saved_measure.py').read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config,indent=2)+'\n'})
        construction = {
            'case_id': case, 'law_id': config['law_id'], 'cell_id': config['cell_id'],
            'actor': config['actor'], 'entrypoint': 'runner.py', 'files': files,
            'recording_description': config['recording_description'],
            'measurement_plan': {'entrypoint': 'lamp_saved_measure.py',
                                 'required_sources': ['vehicle-lamps.jsonl','lamp-context.json',
                                                      'road.xodr','video_frames.jsonl'],
                                 'source_review_required': True},
            'static_checks': ['signed 160m paved road','four cameras and 600 original frames',
                              'Native lamp setting readback and sign/lane survey'],
            'termination_rules': ['600 original frames','restore world and destroy owned actors'],
            'mechanisms': ['Native travel with lamp setting '+('on' if lamp_on else 'off'),
                           'official status and actual photons not claimed'],
            'status': 'partial_native_execution_cpu_checked_physical_unverified',
        }
        path = HERE/'draft-lamp-device'/suffix/'primary'/'construction.json'
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(construction,indent=2)+'\n')
        entries.append({'case_id': case, 'kind': 'delivery',
                        'construction': str(path.relative_to(HERE)),
                        'construction_sha256': sha(path),
                        'candidate_risk': {'status':'physical',
                            'reason':'Actual lamp pixels, traffic-device face and travel route require Native review'},
                        'candidates': [], 'delivery_readiness': 'incomplete'})
    manifest = {'format':'worker-selected-cpu-draft-manifest-v1',
                'assignment_id':ASSIGNMENT,
                'runtime_manifest_sha256':batch['runtime']['source_manifest_sha256'],
                'status':'partial','cases':entries}
    (HERE/'draft-lamp-device-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({'cases':[{'case_id':e['case_id'],'construction_sha256':e['construction_sha256']}
                                for e in entries],
                      'runtime_manifest_sha256':manifest['runtime_manifest_sha256']}))


if __name__ == '__main__':
    main()
