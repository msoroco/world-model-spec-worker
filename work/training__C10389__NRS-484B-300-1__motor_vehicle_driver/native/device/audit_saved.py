"""Independently verify C10389 synthetic raw-to-saved joins and measurements."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit():
    copied = read(HERE / 'offline' / 'manifest.json')
    proof = read(HERE / 'offline' / 'saved-proof.json')
    compatibility = read(HERE / 'offline' / 'saved-compatibility.json')
    if (proof['copied_manifest_sha256'] != sha(HERE / 'offline' / 'manifest.json') or
            compatibility['positive'] != 8 or
            compatibility['tamper_negative'] != 88 or
            compatibility['measured_trigger_positive'] != 2 or
            len(proof['entries']) != 8):
        raise ValueError('saved proof and compatibility')
    by_key = {(row['case_id'], row['candidate_id']): row
              for row in proof['entries']}
    if len(by_key) != 8:
        raise ValueError('saved case uniqueness')
    total = 0
    pairs = {}
    for entry in copied['entries']:
        key = (entry['case_id'], entry['candidate_id'])
        row = by_key[key]
        bundle = HERE / entry['bundle']
        raw = HERE / 'offline' / 'raw-fixtures' / bundle.parent.name / bundle.name
        saved = HERE / 'offline' / 'saved-fixtures' / bundle.parent.name / bundle.name
        if any(row['raw_hashes'][path.name] != sha(path)
               for path in raw.iterdir() if path.is_file()) or \
           any(row['saved_hashes'][path.name] != sha(path)
               for path in saved.iterdir() if path.is_file()):
            raise ValueError('retained fixture hashes')
        cfg = read(bundle / 'config.json')
        receipt = read(saved / 'preparation-receipt.json')
        raw_actors = rows(raw / 'native-raw-actors.jsonl')
        raw_videos = rows(raw / 'video_frames.jsonl')
        raw_reviews = rows(raw / 'frame-review.jsonl')
        observed = rows(saved / 'native-observed.jsonl')
        cameras = rows(saved / 'camera-frames.jsonl')
        reviews = rows(saved / 'frame-review.jsonl')
        requests = rows(bundle / 'requested-tracks.jsonl')
        if (receipt['source_kind'] != 'synthetic_cpu' or
                receipt['original_native_observed'] or receipt['delivery_ready'] or
                receipt['official_placement_verified'] or
                receipt['legal_verdict'] is not None or
                not (len(raw_actors) == len(raw_videos) == len(raw_reviews) == 240) or
                not (len(observed) == len(cameras) == len(reviews) ==
                     len(requests) == 240)):
            raise ValueError('synthetic provenance or cardinality')
        stopped = crossed = face = line = 0
        first = None
        for i, (actor, video, review, obs, camera, saved_review, request) in enumerate(
                zip(raw_actors, raw_videos, raw_reviews, observed, cameras, reviews,
                    requests)):
            native = 1000+i
            if (actor['frame'] != i or actor['native_frame'] != native or
                    video['video_frame'] != i or video['native_frame'] != native or
                    review['frame'] != i or review['native_frame'] != native or
                    obs['frame'] != i or obs['native_frame'] != native or
                    camera['frame'] != i or camera['native_frame'] != native or
                    saved_review != review or obs['ego'] != actor['ego'] or
                    actor['requested_ego_x_m'] != request['requested_ego_x_m'] or
                    actor['requested_speed_mps'] != request['requested_speed_mps']):
                raise ValueError('independent frame join')
            body = obs['ego']['body_native_xyz_m']
            front = max(p[0] for p in body)
            rear = min(p[0] for p in body)
            if front < 50 and obs['ego']['speed_mps'] <= .1:
                stopped += 1
            if front >= 50 and rear <= 50:
                crossed += 1
                if first is None:
                    first = i
            face += int(review['device_face_pixel_reviewed'] and
                        review['device_face_visible'] is True)
            line += int(review['approach_area_pixel_reviewed'] and
                        review['approach_area_visible'] is True)
            total += 1
        measured = row['measurement']
        routed = row['routing']
        if (measured['stopped_before_device_frames'] != stopped or
                measured['front_body_at_device_station_frames'] != crossed or
                measured['first_body_at_device_station_frame'] != first or
                measured['reviewed_visible_device_face_frames'] != face or
                measured['reviewed_visible_approach_area_frames'] != line or
                measured['authored_signal_is_official_placement'] or
                measured['delivery_ready'] or
                routed['triggers']['fallback1']['eligible'] != (
                    cfg['route_policy'] == 'target' and
                    (crossed == 0 or (stopped < 20 if cfg['requested_obey'] else stopped > 0))) or
                routed['triggers']['fallback2']['eligible'] != (face == 0 or line == 0) or
                routed['triggers']['fallback3']['eligible'] is not True or
                routed['selected_fallback'] is not None):
            raise ValueError('independent measurement or fallback')
        pairs.setdefault(cfg['candidate_id'], {})[bundle.parent.name] = (
            cfg['requested_speed_mps'], cfg['camera_policy'], cfg['route_policy'])
    if (len(pairs) != 4 or any(set(pair) != {'probe_1', 'probe_2'} or
                               pair['probe_1'] != pair['probe_2']
                               for pair in pairs.values())):
        raise ValueError('controlled comparison pairs')
    return {'format': 'c10389-device-independent-saved-audit-v1',
            'cases': 8, 'frames_audited': total, 'controlled_pairs': 4,
            'official_placement_verified': False, 'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(audit()))
