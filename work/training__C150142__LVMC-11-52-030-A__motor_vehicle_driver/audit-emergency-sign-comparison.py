"""Check that signed/unsigned emergency drafts isolate the sign request."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def package(case, candidate):
    path = ROOT / ('selected-primary' if candidate == 'primary' else 'selected-fallbacks') / case
    if candidate != 'primary':
        path /= candidate
    files = {row['path']: row['content'] for row in json.loads((path / 'construction.json').read_text())['files']}
    return files, json.loads(files['config.json'])


def check():
    cases = []
    for activity in ('business', 'no_business'):
        unsigned = 'emergency_vehicle_unsigned_' + activity
        signed = 'emergency_vehicle_signed_' + activity
        label = activity.replace('_', '-')
        for candidate in CANDIDATES:
            old_files, old = package(unsigned, candidate)
            new_files, new = package(signed, candidate)
            changed = {key for key in set(old) | set(new) if old.get(key) != new.get(key)}
            if changed != {'case_id', 'selected_case_id', 'supported_case_ids',
                           'sign_classes', 'road_sha256'}:
                raise ValueError('Signed comparison changed fixed config: ' + activity + '/' + candidate)
            if old['sign_classes'] != [] or new['sign_classes'] != ['armored_or_emergency']:
                raise ValueError('Exception sign classes differ')
            for name in ('requested-tracks.jsonl', 'assignment-source.json',
                         'parking_controller.py', 'measure_exceptions.py'):
                if old_files[name] != new_files[name]:
                    raise ValueError('Fixed authored source changed: ' + name)
            old_attempt = REPO / '.runtime-work' / f'c150142-emergency-{label}-{candidate}-native-v1'
            new_attempt = REPO / '.runtime-work' / f'c150142-emergency-signed-{label}-{candidate}-native-v1'
            for name in ('native-raw-actors.jsonl', 'video_frames.jsonl', 'trace.jsonl',
                         'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                         'driver_reference.mkv'):
                if digest(old_attempt / name) != digest(new_attempt / name):
                    raise ValueError('Fixed synthetic source changed: ' + name)
            old_map = json.loads((old_attempt / 'native-map-readback.json').read_text())
            new_map = json.loads((new_attempt / 'native-map-readback.json').read_text())
            if old_map['sign_readback']['present'] or not new_map['sign_readback']['present'] or \
                    new_map['sign_readback']['displayed_classes'] != ['armored_or_emergency']:
                raise ValueError('Source-shaped sign contrast differs')
            if {key for key in old_map if old_map[key] != new_map[key]} != {
                    'sign_readback'}:
                raise ValueError('Other map readback changed')
            cases.append({'activity': activity, 'candidate': candidate,
                          'signed_road_sha256': new['road_sha256'],
                          'fixed_sources_match': True, 'physical_sign_pixels_reviewed': False})
    return {'pairs': cases, 'signed_vs_unsigned_sign_isolated': True,
            'original_native_observed': False, 'legal_verdict': None}


if __name__ == '__main__':
    print(json.dumps(check(), indent=2))
