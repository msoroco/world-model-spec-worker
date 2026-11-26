"""Independent read-only CPU audit of the selected saved diagnostic chain."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
ROOT = PACKAGE.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
SUFFIXES = ('signal_before_safe', 'signal_after_safe',
            'signal_before_unsafe', 'signal_before_no_check')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit(case_id, negative=False):
    require(case_id.startswith(PACKAGE.name + '__'), 'Wrong exact assignment')
    suffix = case_id[len(PACKAGE.name) + 2:]
    require(suffix in SUFFIXES, 'Unknown selected delivery case')
    manifest = json.loads((PACKAGE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case_id), None)
    require(entry is not None, 'Selected case absent from execution manifest')
    expected = '0' * 64 if negative else entry['construction_sha256']
    require(sha(PACKAGE / entry['construction']) == expected,
            'Delivery construction differs from selected manifest')
    scratch = ROOT / '.runtime-work' / 'c245490-owner'
    attempt = scratch / ('compat-' + suffix + '-v5')
    saved_path = scratch / ('saved-' + suffix + '-v2') / 'v0001' / 'processing.json'
    require((attempt / 'compatibility.json').is_file() and saved_path.is_file(),
            'Selected diagnostic capture or saved-only version missing')
    public = json.loads((attempt / 'compatibility.json').read_text())
    saved = json.loads(saved_path.read_text())
    require(public['passed'] is True and public['case_id'] == case_id and
            public['construction_sha256'] == entry['construction_sha256'] and
            public['negative_removed'] == 'native-driver-checks.jsonl',
            'Selected public compatibility or negative source differs')
    require(saved['passed'] is True and saved['recorded_only'] is True and
            saved['case_id'] == case_id and saved['candidate_id'] == 'primary' and
            saved['native_revision']['construction_sha256'] == entry['construction_sha256'] and
            saved['originals_preserved'] is True and saved['missing_evidence'] is False and
            saved['timestamp_joins']['passed'] is True and
            saved['physical_acceptance_claimed'] is False and
            saved['legal_acceptance_claimed'] is False,
            'Selected saved-only processing differs or claims acceptance')
    required = ('native-ego-frames.jsonl', 'native-driver-checks.jsonl',
                'driving-context.json', 'trace.jsonl', 'video_frames.jsonl',
                'capture/evidence.jsonl', *(view + '.mkv' for view in VIEWS))
    hashes = {}
    for name in required:
        source = attempt / name
        require(source.is_file(), 'Missing selected diagnostic source: ' + name)
        digest = sha(source)
        require(saved['original_source_hashes'].get(name) == digest,
                'Saved-only processing changed source: ' + name)
        hashes[name] = digest
    frames = [json.loads(row) for row in (attempt / 'native-ego-frames.jsonl').read_text().splitlines()]
    mapping = [json.loads(row) for row in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    require(len(frames) == len(mapping) == 600 and all(
        row['video_frame'] == i and mapping[i]['video_frame'] == i and
        row['native_frame'] == mapping[i]['native_frame'] and
        abs(row['time_s'] - mapping[i]['time_s']) < 1e-6
        for i, row in enumerate(frames)), 'Selected Native/camera frame joins differ')
    context = json.loads((attempt / 'driving-context.json').read_text())
    require(context['source_kind'] == 'synthetic_native_sample',
            'CPU proof falsely claims original Native provenance')
    checks = [json.loads(row) for row in (attempt / 'native-driver-checks.jsonl').read_text().splitlines()]
    require(len(checks) == 1 and len(set(checks[0]['source_actor_ids'])) == 2 and
            all(row['target_front_surface_gap_m'] >= 0 and
                row['target_rear_surface_gap_m'] >= 0 for row in frames),
            'Independent target-lane front/rear actor source absent')
    result = json.loads(Path(saved['result']).read_text())
    require(result['provenance_kind'] == 'synthetic_fixture' and
            result['diagnostic_fixture'] is True and result['accepted'] is False and
            result['legal_verdict_claimed'] is False and
            result['maneuver_completed'] is False,
            'Diagnostic source promoted to physical or legal acceptance')
    version = saved_path.parent
    require((version / 'final-decode.json').is_file() and
            all((version / ('source-' + str(i) + '.json')).is_file() for i in range(4)),
            'Four source videos or composed final video lack decode audit')
    physical = json.loads((PACKAGE / entry['physical_preparation']['receipt']).read_text())
    require(physical['original_native_motion_verified'] is False and
            {item['kind'] for item in physical['fixtures']} ==
            {'complete_motion', 'incomplete_motion', 'missing_evidence'},
            'Synthetic physical outcomes were promoted')
    return {'case_id': case_id, 'source_sha256': hashes,
            'joined_frames': 600, 'front_and_rear_source_distinct': True,
            'four_camera_sources': list(VIEWS),
            'saved_recorded_only': True, 'original_native_motion_verified': False,
            'actual_pixels_reviewed': False, 'physical_delivery_accepted': False,
            'legal_verdict_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.negative), allow_nan=False))


if __name__ == '__main__':
    main()
