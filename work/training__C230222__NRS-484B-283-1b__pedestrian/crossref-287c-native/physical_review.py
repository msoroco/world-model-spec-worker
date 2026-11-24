"""Independent original-source review for the adjacent-device 287(c) pair."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET

CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
ROLES = {'south': '28701', 'north': '28702'}
ASSIGNMENT = 'training__C230222__NRS-484B-283-1b__pedestrian'


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def inspect_road(content, marked):
    root = ET.fromstring(content)
    roads = root.findall('road')
    junctions = root.findall('junction')
    signals = root.findall('.//signals/signal')
    marks = [item for item in root.findall('.//objects/object')
             if item.get('type') == 'crosswalk']
    require(len(roads) == 11 and len(junctions) == 2,
            'Original Native adjacent-intersection topology differs')
    require({x.get('id') for x in junctions} == {'1', '2'} and
            all(len(x.findall('connection')) == 4 for x in junctions),
            'Original Native adjacent-intersection connections differ')
    require({x.get('id') for x in signals} == set(ROLES.values()) and
            all(x.get('dynamic') == 'yes' for x in signals),
            'Original Native adjacent-device targets differ')
    require(len(marks) == int(marked) and
            all(x.get('s') == '26.5' for x in marks),
            'Original Native marked crossing differs')
    return {'road_count': len(roads), 'junction_count': len(junctions),
            'device_count': len(signals), 'marking_count': len(marks)}


def inspect_frames(samples, frame_map):
    require(len(samples) == len(frame_map) == 600,
            'Complete original Native device and frame source required')
    actors = {}
    for index, (sample, frame) in enumerate(zip(samples, frame_map)):
        native_frame = sample.get('native_frame')
        require(frame.get('video_frame') == index and
                frame.get('native_frame') == native_frame and
                frame.get('carla_frame') == native_frame and
                abs(frame.get('time_s', -1) - sample.get('time_s', -2)) < 1e-4,
                'Original Native device frame join differs')
        devices = sample.get('adjacent_device_readback')
        require(isinstance(devices, dict) and set(devices) == set(ROLES),
                'Both original Native device readbacks required')
        for role, opendrive_id in ROLES.items():
            entry = devices[role]
            actor_id = entry.get('native_actor_id')
            require(entry.get('opendrive_id') == opendrive_id and
                    entry.get('source') == 'native_readback' and
                    entry.get('raw_state') in ('red', 'yellow', 'green') and
                    isinstance(actor_id, int) and actor_id > 0,
                    'Original Native operating device readback differs')
            if role in actors:
                require(actors[role] == actor_id,
                        'Original Native device actor changed during capture')
            actors[role] = actor_id
    require(actors['south'] != actors['north'],
            'Two distinct original Native devices required')
    return actors


def audit(attempt, review_path):
    attempt = Path(attempt)
    config = read(attempt / 'config.json')
    case_id = config.get('case_id') or config.get('selected_case_id')
    require(case_id in (ASSIGNMENT + '__crossref_287c_marked',
                        ASSIGNMENT + '__crossref_287c_unmarked'),
            'Exact 287(c) case required')
    marked = case_id.endswith('_marked') and not case_id.endswith('_unmarked')
    review = read(review_path)
    require(review.get('case_id') == case_id and
            review.get('provenance') == 'original_native' and
            isinstance(review.get('reviewer'), str) and review['reviewer'].strip(),
            'Independent original Native review required')
    seal = attempt / 'capture-seal.json'
    context_path = attempt / 'curb-context.json'
    native_road = attempt / 'native-road.xodr'
    require(review.get('capture_seal_sha256') == sha(seal) and
            review.get('curb_context_sha256') == sha(context_path),
            'Original capture seal and road context review binding required')
    context = read(context_path)
    require(context.get('source_kind') == 'native_observation' and
            context.get('native_road_sha256') == sha(native_road) and
            context.get('authored_road_sha256') == sha(attempt / 'road.xodr') and
            review.get('native_road_sha256') == sha(native_road),
            'Original Native road source hash differs')
    road = inspect_road(native_road.read_bytes(), marked)
    samples = [json.loads(line) for line in (attempt / 'curb-samples.jsonl').read_text().splitlines()]
    frame_map = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    require(review.get('curb_samples_sha256') == sha(attempt / 'curb-samples.jsonl') and
            review.get('frame_map_sha256') == sha(attempt / 'video_frames.jsonl'),
            'Original Native device and frame source hash differs')
    actors = inspect_frames(samples, frame_map)
    for name in ('actual_device_pixels_reviewed', 'official_device_status_reviewed',
                 'crossing_marking_pixels_reviewed', 'pedestrian_crossing_path_reviewed',
                 'physical_completion_reviewed'):
        require(review.get(name) is True,
                'Original 287(c) physical review missing: ' + name)
    reviewed_frames = review.get('reviewed_frames')
    require(isinstance(reviewed_frames, list) and reviewed_frames and
            all(type(value) is int and 0 <= value < 600 for value in reviewed_frames),
            'Original reviewed frame IDs required')
    hashes = review.get('source_video_sha256')
    require(isinstance(hashes, dict) and set(hashes) == set(CAMERAS),
            'Four original source video hashes required')
    for camera in CAMERAS:
        video = attempt / (camera + '.mkv')
        require(sha(video) == hashes[camera],
                'Original source video changed: ' + camera)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames',
                                '-select_streams', 'v:0', '-show_entries',
                                'stream=nb_read_frames', '-of',
                                'default=nokey=1:noprint_wrappers=1', str(video)],
                               capture_output=True, text=True, check=True)
        require(probe.stdout.strip() == '600',
                'Complete original source video required: ' + camera)
    return {'format': 'c230222-287c-original-source-review-v1',
            'case_id': case_id, 'capture_seal_sha256': sha(seal),
            'native_road_sha256': sha(native_road), 'road_shape': road,
            'native_device_actor_ids': actors, 'reviewed_frames': reviewed_frames,
            'source_video_sha256': hashes, 'legal_applicability_conclusion': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--review', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(args.attempt, args.review), indent=2) + '\n')
