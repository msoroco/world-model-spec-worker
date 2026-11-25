"""Exercise the bundled 600-frame saved meters with source-shaped CPU packets."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c422978-30s-saved'
SOURCE = ROOT / '.runtime-work/c422978-30s-v5'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def run(program, *args):
    process = subprocess.run([sys.executable, str(program), *map(str, args)],
                             text=True, capture_output=True)
    return process


def build(case, candidate):
    bundle = SOURCE / (case + '-' + candidate)
    folder = SCRATCH / (case + '-' + candidate)
    folder.mkdir(parents=True, exist_ok=True)
    observed = []
    mapping = []
    captured = []
    for request in rows(bundle / 'requested-tracks.jsonl'):
        index = request['frame']
        x, requested_y = request['requested_center_xy_m']
        y = -requested_y
        frame = 1000 + index
        observed.append({'frame': index, 'native_frame': frame,
                         'time_s': request['time_s'], 'source_kind': 'synthetic_cpu',
                         'motorcycle_blueprint': request['motorcycle_blueprint'],
                         'center_native_xy_m': [x, y],
                         'body_native_xy_m': [[round(x + dx, 4), round(y + dy, 4)]
                                              for dx, dy in ((-1.1, -.4), (-1.1, .4),
                                                             (1.1, -.4), (1.1, .4))],
                         'speed_mps': request['requested_speed_mps'],
                         'native_road_id': 1, 'native_lane_id': -2 if y >= 3.5 else -1})
        mapping.append({'video_frame': index, 'native_frame': frame,
                        'carla_frame': frame, 'time_s': request['time_s']})
        captured.append({'original_frame': frame,
                         'recording_time_s': request['time_s']})
    for name, values in (('native-observed.jsonl', observed),
                         ('video_frames.jsonl', mapping),
                         ('capture/evidence.jsonl', captured)):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in values))
    native_map = folder / 'native-map-readback.json'
    write(native_map, {'sidewalk_road_id': 1, 'sidewalk_lane_id': -2,
                       'motorcycle_blueprint': 'vehicle.kawasaki.ninja',
                       'city_location_verified': False, 'source_kind': 'synthetic_cpu'})
    context = folder / 'city-context.json'
    write(context, {'format': 'c422978-spatial-context-v1',
                    'law_id': 'LVMC-11-38-030', 'authority_kind': 'synthetic_cpu',
                    'city_authority_reviewed': False,
                    'map_readback_sha256': sha(native_map),
                    'native_to_context_affine': [[1, 0, 0], [0, 1, 0]],
                    'city_boundary_polygon': [[-1, 0], [141, 0], [141, 7], [-1, 7]],
                    'sidewalk_polygon': [[0, 3.5], [140, 3.5], [140, 5.5], [0, 5.5]],
                    'driveway_crossing_polygons': []})
    return bundle, folder


def main():
    results = []
    for candidate in ('primary', 'fallback1', 'fallback3'):
      for case in ('witness_1', 'witness_2'):
        bundle, folder = build(case, candidate)
        occupancy = run(bundle / 'measure_saved.py', folder)
        context = run(bundle / 'measure_context.py', '--attempt', folder,
                      '--context', folder / 'city-context.json')
        if occupancy.returncode or context.returncode:
            raise ValueError('Bundled saved meter failed: ' + occupancy.stderr + context.stderr)
        saved = json.loads(occupancy.stdout)
        spatial = json.loads(context.stdout)
        expected = case == 'witness_2'
        if (saved['frames'] != 600 or spatial['frames'] != 600 or
                bool(saved['moving_sidewalk_overlap_frames']) != expected or
                bool(spatial['candidate_city_sidewalk_non_driveway_frames']) != expected or
                saved['source_kind'] != 'synthetic_cpu' or
                spatial['city_authority_reviewed'] is not False or
                spatial['legal_verdict'] is not None):
            raise ValueError('Thirty-second saved measurement differs')
        construction = (HERE / 'extended-primary' / case /
                        ('construction.json' if candidate == 'primary' else candidate + '/construction.json'))
        results.append({'case_id': json.loads((bundle / 'config.json').read_text())['case_id'],
                        'candidate_id': candidate,
                        'construction_sha256': sha(construction),
                        'meter_sha256': sha(bundle / 'measure_saved.py'),
                        'context_meter_sha256': sha(bundle / 'measure_context.py'),
                        'source_hashes': saved['source_hashes'],
                        'context_sha256': sha(folder / 'city-context.json'),
                        'moving_overlap_frames': saved['moving_sidewalk_overlap_frames'],
                        'candidate_city_sidewalk_frames': spatial['candidate_city_sidewalk_non_driveway_frames']})
    bundle, folder = SOURCE / 'witness_2-primary', SCRATCH / 'witness_2-primary'
    observed = folder / 'native-observed.jsonl'
    saved_bytes = observed.read_bytes()
    observed.unlink()
    missing = run(bundle / 'measure_saved.py', folder)
    observed.write_bytes(saved_bytes)
    if missing.returncode == 0 or 'Missing required source: native-observed.jsonl' not in missing.stderr:
        raise ValueError('Missing Native source was accepted')
    frame_map = folder / 'video_frames.jsonl'
    original_frames = frame_map.read_bytes()
    corrupted = rows(frame_map)
    corrupted[90]['native_frame'] = 2000
    frame_map.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in corrupted))
    unjoined = run(bundle / 'measure_saved.py', folder)
    frame_map.write_bytes(original_frames)
    if unjoined.returncode == 0 or 'Original Native/video/capture frame join differs' not in unjoined.stderr:
        raise ValueError('Changed Native/video frame join was accepted')
    packet = folder / 'city-context.json'
    original = packet.read_bytes()
    changed = json.loads(original)
    changed['map_readback_sha256'] = '0' * 64
    write(packet, changed)
    stale = run(bundle / 'measure_context.py', '--attempt', folder, '--context', packet)
    packet.write_bytes(original)
    if stale.returncode == 0 or 'Spatial context map readback hash differs' not in stale.stderr:
        raise ValueError('Stale city context was accepted')
    changed = json.loads(original)
    changed['city_authority_reviewed'] = True
    write(packet, changed)
    false_authority = run(bundle / 'measure_context.py', '--attempt', folder,
                          '--context', packet)
    packet.write_bytes(original)
    if false_authority.returncode == 0 or 'City authority review cannot be claimed' not in false_authority.stderr:
        raise ValueError('False city authority claim was accepted')
    report = {'format': 'c422978-30s-saved-source-proof-v1', 'selected': False,
              'synthetic_only': True, 'original_native_observed': False,
              'city_authority_reviewed': False, 'legal_verdict': None,
              'results': results, 'negative_rejections': [
                  'Missing required source: native-observed.jsonl',
                  'Original Native/video/capture frame join differs',
                  'Spatial context map readback hash differs',
                  'City authority review cannot be claimed by packet']}
    output = HERE / 'extended-primary/saved-proof.json'
    output.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'proof_sha256': sha(output),
                      'overlap': [item['moving_overlap_frames'] for item in results],
                      'negatives': len(report['negative_rejections'])}))


if __name__ == '__main__':
    main()
