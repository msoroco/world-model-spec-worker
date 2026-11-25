"""Independent source-bound CPU delivery rehearsal for exact zone-crossing cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = {'probe_1': 'selected-probe1', 'probe_2': 'selected-probe2',
          'traffic_clear_traffic': 'selected-traffic-clear_traffic',
          'traffic_following_brake': 'selected-traffic-following_brake'}
REQUIRED = {'actual_analysis', 'native_validation', 'mandatory_observations',
            'lean_decoder', 'render', 'final_decode', 'four_camera_sources',
            'selected_measurements', 'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def check(case_id, diagnostic):
    if not diagnostic:
        raise ValueError('Original Native source required for delivery acceptance')
    manifest = read(HERE / 'execution-manifest.json')
    entries = [item for item in manifest['cases'] if item['case_id'] == case_id]
    if len(entries) != 1:
        raise ValueError('Select one exact case')
    entry = entries[0]
    suffix = case_id.split('__')[-1]
    if suffix not in PREFIX:
        raise ValueError('Unknown exact case')
    prefix = PREFIX[suffix]
    fixture = HERE / (prefix + '-fixture')
    actor_path = fixture / 'native-raw-actors.jsonl'
    frame_path = fixture / 'video_frames.jsonl'
    review_path = fixture / 'review.json'
    actors = [json.loads(line) for line in actor_path.read_text().splitlines()]
    frames = [json.loads(line) for line in frame_path.read_text().splitlines()]
    review = read(review_path)
    if (len(actors) != 600 or len(frames) != 600 or
            any(a.get('frame') != i or a.get('native_frame') != 1000 + i or
                abs(a.get('time_s', 0) - (i + 1) / 20) > 1e-4 or
                not all(k in a for k in ('ego', 'oncoming', 'following'))
                for i, a in enumerate(actors)) or
            review.get('source_kind') != 'synthetic_fixture' or
            review.get('case_id') != case_id or
            review.get('raw_sha256') != sha(actor_path) or
            review.get('video_frames_sha256') != sha(frame_path)):
        raise ValueError('Diagnostic actor, participant or frame source join differs')
    public_path = HERE / (prefix + '-compatibility.json')
    saved_path = HERE / (prefix + '-processing.json')
    public, saved = read(public_path), read(saved_path)
    if (not public['passed'] or public['case_id'] != case_id or
            public['candidate_id'] != 'primary' or
            public['construction_sha256'] != entry['construction_sha256'] or
            public['runtime_manifest_sha256'] != manifest['runtime_manifest_sha256'] or
            not REQUIRED <= set(public['checks']) or
            public['measurement_examples'][next(iter(public['measurement_examples']))]['sources']['native-raw-actors.jsonl'] != sha(actor_path)):
        raise ValueError('Exact current-runtime source compatibility missing')
    if (not saved['passed'] or not saved['recorded_only'] or
            not saved['originals_preserved'] or saved['case_id'] != case_id or
            saved['candidate_id'] != 'primary' or
            saved['timestamp_joins'].get('frames') != 600):
        raise ValueError('Recorded-only original-source processing missing')
    physical_path = HERE / entry['physical_preparation']['receipt']
    physical = read(physical_path)
    if (sha(physical_path) != entry['physical_preparation']['sha256'] or
            physical['original_native_observed'] is not False or
            physical['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Diagnostic physical preparation changed')
    return {'case_id': case_id, 'diagnostic_only': True,
            'physical_acceptance': False, 'legal_verdict': None,
            'source_kind': 'synthetic_fixture', 'joined_frames': 600,
            'compatibility_sha256': sha(public_path),
            'saved_processing_sha256': sha(saved_path),
            'actor_frames_sha256': sha(actor_path),
            'frame_map_sha256': sha(frame_path),
            'review_sha256': sha(review_path)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.diagnostic), sort_keys=True))
