"""Build two exact unselected CPU bundles from this assignment's sources."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NATIVE = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    entries = []
    for suffix, signal, pause in (('probe_a', 80, True), ('probe_b', None, True),
                                  ('probe_c', 80, False)):
        case = ASSIGNMENT + '__' + suffix
        config = {'case_id': case, 'selected_case_id': case,
                  'cell_id': 'C230266', 'law_id': 'LVMC-11-40-180-C',
                  'actor': 'cycle_or_scooter_operator', 'duration_s': 30,
                  'rate_hz': 20, 'device_blueprint_filter': 'vehicle.diamondback.century',
                  'pedestrian_blueprint_filter': 'walker.pedestrian.*',
                  'signal_frame': signal, 'pause_window_frames': [80, 110] if pause else [0, 0],
                  'pedestrian_microphone': {'location': 'pedestrian_actor',
                                            'sampling': 'synchronized_original_audio_required'},
                  'cameras': [{'name': name, 'width': 1280, 'height': 720}
                              for name in ('overview', 'rider_approach', 'pedestrian_side', 'pass_close')],
                  'required_atoms': ['ru.pedestrian', 'kin.position', 'kin.speed'],
                  'source_packets': []}
        files = []
        for source, target in ((NATIVE/'runner.py', 'runner.py'),
                               (NATIVE/'road.xodr', 'road.xodr'),
                               (NATIVE/'tests/test_offline.py', 'tests/test_offline.py')):
            files.append({'path': target, 'content': source.read_text()})
        files.append({'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'})
        construction = {'case_id': case, 'cell_id': 'C230266',
                        'law_id': 'LVMC-11-40-180-C', 'actor': 'cycle_or_scooter_operator',
                        'entrypoint': 'runner.py', 'files': files,
                        'recording_description': {'channels': [
                            {'name': 'rider_and_pedestrian_footprints', 'sampling_rate_hz': 20,
                             'source': 'original Native transforms and bounding boxes'},
                            {'name': 'pedestrian_location_audio', 'sampling_rate_hz': 20,
                             'source': 'synchronized original microphone stream at pedestrian location'}],
                             'limitations': ['Native rider-device capability and original audio unverified']},
                        'status': 'unselected_exact_cpu_draft'}
        path = ROOT/'native-draft'/suffix/'construction.json'
        dump(path, construction)
        entries.append({'case_id': case, 'kind': 'draft_not_selected',
                        'construction': str(path.relative_to(ROOT)),
                        'construction_sha256': sha(path), 'candidates': [],
                        'candidate_risk': {'status': 'physical',
                                           'reason': 'Native device motion and pedestrian-location audio not yet tested'}})
    dump(ROOT/'native-draft-manifest.json', {
        'format': 'worker-unselected-draft-construction-manifest-v1',
        'assignment_id': ASSIGNMENT, 'status': 'draft_not_selected',
        'cases': entries, 'original_native_observed': False, 'delivery_ready': False})


if __name__ == '__main__':
    main()
