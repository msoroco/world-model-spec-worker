"""Exercise saved geometry logic on retained synthetic Native-shaped rows."""
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('c104538_saved_geometry', HERE/'native/measure_geometry.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in path.read_text().splitlines() if x.strip()]


def unreviewed(source):
    return [{**row, 'mounted': None, 'walking_machine': None,
             'u_turn_active': None, 'posture_source': 'original_pixel_review_pending',
             'turn_source': 'saved_geometry_review_pending'} for row in source]


def rejected(rider, native, mapping, sign, change):
    r = [dict(x) for x in rider]
    n = [dict(x) for x in native]
    m = [dict(x) for x in mapping]
    if change == 'filled_posture':
        r[250]['mounted'] = True
    elif change == 'changed_actor':
        r[250]['actor_id'] = 'other-rider'
    elif change == 'changed_sign':
        r[250]['sign_id'] = 'other-sign'
    elif change == 'changed_frame':
        m[250]['video_frame'] = 249
    elif change == 'changed_center':
        n[250] = {**n[250], 'native_center_xy_m': [999, 999]}
    elif change == 'changed_station':
        sign = {**sign, 'station_m': 42.0}
    else:
        raise ValueError(change)
    try:
        module.measure(r, n, m, sign)
    except ValueError as exc:
        return str(exc)
    return None


def main():
    entries = []
    for kind in ('mounted_obey', 'mounted_turn'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            folder = HERE/'draft-exact-candidates'/kind/candidate/'package-proof'
            paths = {name: folder/name for name in ('rider_native_samples.jsonl',
                'native_samples.jsonl', 'video_frames.jsonl', 'authored-sign.json')}
            rider = unreviewed(rows(paths['rider_native_samples.jsonl']))
            native = rows(paths['native_samples.jsonl'])
            mapping = rows(paths['video_frames.jsonl'])
            sign = json.loads(paths['authored-sign.json'].read_text())
            measurement = module.measure(rider, native, mapping, sign)
            if measurement['u_turn_geometry_observed'] != (kind == 'mounted_turn'):
                raise ValueError('Controlled saved geometry contrast differs')
            negatives = {name: rejected(rider, native, mapping, sign, name) for name in
                ('filled_posture', 'changed_actor', 'changed_sign', 'changed_frame',
                 'changed_center', 'changed_station')}
            if not all(negatives.values()):
                raise ValueError('Altered saved source was accepted')
            entries.append({'kind': kind, 'candidate_id': candidate,
                'source_sha256': {name: sha(path) for name, path in paths.items()},
                'measurement': measurement, 'negative_rejections': negatives})
    result = {'format': 'c104538-lvmc-saved-geometry-diagnostic-v1',
        'scope': 'unselected synthetic source rows with posture labels erased',
        'entries': entries, 'positive_count': 8, 'negative_count': 48,
        'original_native_capture_executed': False, 'posture_reviewed': False,
        'legal_verdict_claimed': False, 'accepted': False}
    target = HERE/'draft-saved-geometry-proof.json'
    target.write_text(json.dumps(result, indent=2, sort_keys=True)+'\n')
    print(json.dumps({'positives': 8, 'negatives': 48, 'sha256': sha(target)}))


if __name__ == '__main__':
    main()
