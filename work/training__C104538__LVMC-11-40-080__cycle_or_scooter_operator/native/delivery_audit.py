"""Independent source review for rider sign, posture, movement and pixels."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

ASSIGNMENT = 'training__C104538__LVMC-11-40-080__cycle_or_scooter_operator'
KINDS = {'controlled_1': 'mounted-obey', 'controlled_2': 'mounted-turn',
         'controlled_3': 'dismounted-turn'}
for _machine in ('electric_bicycle', 'electric_scooter'):
    KINDS.update({f'{_machine}_obey': 'mounted-obey',
                  f'{_machine}_turn': 'mounted-turn',
                  f'{_machine}_dismount': 'dismounted-turn'})
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def require(ok, message):
    if not ok:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source(root, name):
    root = Path(root).resolve()
    path = (root / name).resolve()
    require(root in path.parents and path.is_file(), 'Missing delivery source: ' + name)
    return path


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def decode(path, expected=600):
    run = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                          '-show_entries', 'stream=nb_read_frames', '-of', 'json', str(path)],
                         capture_output=True, text=True, timeout=180)
    streams = json.loads(run.stdout).get('streams', []) if run.returncode == 0 else []
    require(len(streams) == 1 and int(streams[0].get('nb_read_frames', 0)) == expected,
            'Full video frame count differs')
    return {'frames': expected, 'sha256': sha(path)}


def check_sources(attempt, case, diagnostic=False):
    suffix = case.rsplit('__', 1)[-1]
    require(case == ASSIGNMENT + '__' + suffix and suffix in KINDS, 'Wrong delivery case')
    attempt = Path(attempt)
    paths = {name: source(attempt, name) for name in
             ('trace.jsonl', 'video_frames.jsonl', 'native_samples.jsonl',
              'rider_native_samples.jsonl', 'sign-review.json', 'pixel_review.jsonl')}
    trace, mapping, native, rider, marks = (rows(paths[name]) for name in
        ('trace.jsonl', 'video_frames.jsonl', 'native_samples.jsonl',
         'rider_native_samples.jsonl', 'pixel_review.jsonl'))
    require(all(len(item) == 600 for item in (trace, mapping, native, rider, marks)),
            'Native/rider/pixel time join incomplete')
    expected_machine = suffix.rsplit('_', 1)[0] if suffix.startswith(('electric_bicycle_', 'electric_scooter_')) else 'bicycle'
    require(all(row.get('machine_class') == expected_machine for row in rider),
            'Delivery machine class differs from selected case')
    for i, (t, m, n, r, pixel) in enumerate(zip(trace, mapping, native, rider, marks)):
        require(m.get('video_frame') == r.get('frame') == pixel.get('frame') == i and
                m.get('carla_frame') == t.get('frame') == n.get('native_frame') and
                abs(t['time_s'] - m['time_s']) < 1e-6 and
                abs(n['time_s'] - m['time_s']) < 1e-6 and
                abs(r['time_s'] - m['time_s']) < 1e-6,
                'Native/rider/pixel time join differs')
        require(type(pixel.get('sign_visible')) is bool and
                type(pixel.get('rider_visible')) is bool and
                type(pixel.get('machine_visible')) is bool,
                'Original pixel marks incomplete')
    review = json.loads(paths['sign-review.json'].read_text())
    require(review.get('native_samples_sha256') == sha(paths['native_samples.jsonl']) and
            review.get('frame_map_sha256') == sha(paths['video_frames.jsonl']) and
            review.get('rider_samples_sha256') == sha(paths['rider_native_samples.jsonl']) and
            review.get('pixel_review_sha256') == sha(paths['pixel_review.jsonl']),
            'Original review source hash differs')
    require(review.get('sign_code') == 'no_u_turn' and
            review.get('governs_approach') is True,
            'Applicable prohibition device unverified')
    if diagnostic:
        return {'case_id': case, 'diagnostic_fixture': True, 'join_frames': 600,
                'original_native_observed': False, 'physical_acceptance_claimed': False}
    labels_path = source(attempt, 'rider-review.jsonl')
    labels = rows(labels_path)
    require(len(labels) == 600 and review.get('rider_review_sha256') == sha(labels_path),
            'Original rider review source binding differs')
    require(all(label.get('frame') == i and label.get('actor_id') == rider[i].get('actor_id')
                for i, label in enumerate(labels)), 'Original rider review actor/frame join differs')
    if expected_machine != 'bicycle':
        binding_path = source(attempt, 'electric-asset-binding.json')
        asset_path = source(attempt, 'electric-asset-review.json')
        seal = json.loads(source(attempt, 'capture-seal.json').read_text())
        binding = json.loads(binding_path.read_text())
        asset = json.loads(asset_path.read_text())
        require(binding.get('machine_class') == expected_machine and
                binding.get('blueprint_id') == asset.get('blueprint_id') and
                binding.get('classification_review_record_bound') is True and
                binding.get('legal_verdict_claimed') is False and
                seal.get('sources', {}).get('electric-asset-binding.json') == sha(binding_path) and
                seal.get('sources', {}).get('electric-asset-review.json') == sha(asset_path),
                'Reviewed electric Native asset source binding differs')
        require(bool(binding.get('review_source_sha256')), 'Reviewed electric class sources missing')
        for relative, digest in binding['review_source_sha256'].items():
            target = source(attempt, 'electric-asset-sources/' + relative)
            require(sha(target) == digest and seal.get('sources', {}).get(
                    'electric-asset-sources/' + relative) == digest,
                    'Reviewed electric asset source differs')
    require(review.get('source_kind') == 'original_camera_sign_and_rider_review' and
            review.get('reviewed_from_original_pixels') is True and
            review.get('official_device_verified') is True and
            review.get('rider_posture_verified') is True,
            'Original sign/rider pixel and designation review missing')
    if suffix == 'controlled_3' or suffix.endswith('_dismount'):
        dismount = next((i for i, row in enumerate(labels) if row['mounted'] is False), None)
        turning = next((i for i, row in enumerate(labels) if row['u_turn_active'] is True), None)
        require(dismount is not None and turning is not None and dismount < turning and
                all(row['walking_machine'] is True and row['mounted'] is False
                    for row in labels if row['u_turn_active'] is True) and
                review.get('pedestrian_rule_compliance_verified') is True,
                'Original dismount or pedestrian-rule conduct unverified')
    videos = {view: decode(source(attempt, view + '.mkv')) for view in VIEWS}
    primary = decode(source(attempt, 'raw.mkv'))
    require(review.get('approach_video_sha256') == videos['approach']['sha256'],
            'Original approach pixels differ from review')
    result = json.loads(source(attempt, 'result.json').read_text())
    require(result.get('case_id') == case and result.get('provenance_kind') != 'synthetic_fixture'
            and result.get('maneuver_completed') is True,
            'Original Native physical completion unverified')
    return {'format': 'worker-delivery-audit', 'case_id': case, 'passed': True,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'source_hashes': {name: sha(path) for name, path in paths.items()},
            'source_decodes': videos, 'primary_decode': primary,
            'legal_verdict_claimed': False}


def selftest(case, negative):
    here = Path(__file__).resolve().parents[1]
    repo = here.parents[1]
    suffix = case.rsplit('__', 1)[-1]
    require(case == ASSIGNMENT + '__' + suffix and suffix in KINDS, 'Wrong selftest case')
    package = here / ('v2-' + KINDS[suffix] + '-primary-source')
    electric_rider = here / 'electric-drafts' / suffix / 'rider_native_samples.jsonl'
    with tempfile.TemporaryDirectory(dir=repo / '.runtime-work', prefix='c104538-rider-audit-') as tmp:
        stage = Path(tmp)
        for name in ('trace.jsonl', 'video_frames.jsonl', 'native_samples.jsonl',
                     'rider_native_samples.jsonl'):
            origin = electric_rider if name == 'rider_native_samples.jsonl' and suffix.startswith(('electric_bicycle_', 'electric_scooter_')) else package / name
            (stage / name).write_bytes(origin.read_bytes())
        marks = [{'frame': i, 'sign_visible': True, 'rider_visible': True,
                  'machine_visible': True} for i in range(600)]
        (stage / 'pixel_review.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in marks))
        packet = {'source_kind': 'synthetic_diagnostic', 'sign_code': 'no_u_turn',
                  'governs_approach': True,
                  'native_samples_sha256': sha(stage / 'native_samples.jsonl'),
                  'frame_map_sha256': sha(stage / 'video_frames.jsonl'),
                  'rider_samples_sha256': sha(stage / 'rider_native_samples.jsonl'),
                  'pixel_review_sha256': sha(stage / 'pixel_review.jsonl')}
        (stage / 'sign-review.json').write_text(json.dumps(packet) + '\n')
        if negative:
            (stage / 'rider_native_samples.jsonl').unlink()
        result = check_sources(stage, case, diagnostic=True)
        if not negative:
            video = stage / 'decode-test.mkv'
            subprocess.run(['ffmpeg', '-nostdin', '-hide_banner', '-loglevel', 'error',
                            '-f', 'lavfi', '-i', 'color=c=black:s=64x36:r=20',
                            '-frames:v', '600', '-an', '-c:v', 'ffv1', '-threads', '1',
                            str(video)], check=True, timeout=180)
            result['decode'] = decode(video)
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt')
    parser.add_argument('--selftest', action='store_true')
    parser.add_argument('--negative-selftest', action='store_true')
    args = parser.parse_args()
    if args.selftest or args.negative_selftest:
        result = selftest(args.case, args.negative_selftest)
    else:
        require(args.attempt, 'Original attempt required')
        result = check_sources(args.attempt, args.case)
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
