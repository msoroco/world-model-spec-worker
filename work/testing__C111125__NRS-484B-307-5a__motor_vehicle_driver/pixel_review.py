"""Check source-bound visual review against decoded original camera pixels.

The reviewer supplies the visual interpretation. This module checks its source,
frame, crop, and nonblank pixels; contrast alone cannot identify an arrow or body.
"""
import hashlib
import json
import subprocess
from pathlib import Path


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CLAIMS = ('sole_straight_arrow_visible', 'participant_visible')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(video):
    result = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json', str(video)],
        check=True, capture_output=True, text=True)
    streams = json.loads(result.stdout)['streams']
    if len(streams) != 1:
        raise ValueError('original camera has no unique video stream')
    row = streams[0]
    return int(row['width']), int(row['height']), int(row['nb_read_frames'])


def crop_pixels(video, frame, roi):
    x, y, width, height = roi
    result = subprocess.run(
        ['ffmpeg', '-nostdin', '-v', 'error', '-i', str(video),
         '-vf', f'select=eq(n\\,{frame}),crop={width}:{height}:{x}:{y},format=gray',
         '-frames:v', '1', '-f', 'rawvideo', '-'],
        check=True, capture_output=True)
    if len(result.stdout) != width * height:
        raise ValueError('original camera crop failed to decode requested frame')
    return result.stdout


def audit(attempt, packet_path, seal, acquisition, frame_count, occupied,
          signals, traffic, context):
    """Return hashes of reviewed crops; reject stale or empty visual evidence."""
    attempt = Path(attempt)
    packet = json.loads(Path(packet_path).read_text())
    if packet.get('format') != 'c111125-original-pixel-review-v1' or not packet.get('reviewer'):
        raise ValueError('original pixel review packet or reviewer absent')
    observations = packet.get('observations')
    if not isinstance(observations, list) or not observations:
        raise ValueError('original pixel review observations absent')
    dimensions = {}
    for name in CAMERAS:
        source = name + '.mkv'
        path = attempt / source
        if source not in seal['sources'] or not path.is_file() or sha(path) != seal['sources'][source]:
            raise ValueError('original camera source missing or changed: ' + source)
        if acquisition.get(source, {}).get('kind') != 'original_native' or acquisition[source].get('sha256') != sha(path):
            raise ValueError('original camera acquisition missing or stale: ' + source)
        dimensions[name] = probe(path)
        if dimensions[name][2] != frame_count:
            raise ValueError('original camera frame count differs from Native frame map')
    claims = set()
    receipts = []
    for item in observations:
        if not isinstance(item, dict) or item.get('claim') not in CLAIMS or item.get('camera') not in CAMERAS:
            raise ValueError('original pixel review claim or camera invalid')
        camera = item['camera']
        source = camera + '.mkv'
        if item.get('source_sha256') != seal['sources'][source]:
            raise ValueError('original pixel review source hash differs')
        frame = item.get('video_frame')
        roi = item.get('roi_xywh')
        if type(frame) is not int or not 0 <= frame < frame_count or \
           not isinstance(roi, list) or len(roi) != 4 or \
           not all(type(value) is int for value in roi):
            raise ValueError('original pixel review frame or crop invalid')
        x, y, width, height = roi
        image_width, image_height, _ = dimensions[camera]
        if x < 0 or y < 0 or width < 4 or height < 4 or \
           x + width > image_width or y + height > image_height:
            raise ValueError('original pixel review crop outside camera frame')
        if item['claim'] == 'sole_straight_arrow_visible':
            if item.get('actor_id') != context['facing_head_id'] or \
               signals[frame].get('aspect', {}).get('source_verified') is not True:
                raise ValueError('original pixel arrow claim differs from verified frame')
        else:
            from runner import overlaps
            regions = [context['intersection_bounds_m'],
                       *context['adjacent_crosswalk_bounds_m']]
            actors = [person for person in traffic[frame]['participants']
                      if person['id'] == item.get('actor_id') and
                      person.get('lawfully_present') is True and
                      any(overlaps(person['body_vertices_m'], region) for region in regions)]
            if len(actors) != 1:
                raise ValueError('original pixel participant claim differs from lawful occupied frame')
        pixels = crop_pixels(attempt / source, frame, roi)
        if max(pixels) - min(pixels) < 12:
            raise ValueError('original pixel review crop lacks visible contrast')
        claims.add(item['claim'])
        receipts.append({'claim': item['claim'], 'camera': camera,
                         'video_frame': frame, 'actor_id': item['actor_id'],
                         'roi_xywh': roi,
                         'crop_gray_sha256': hashlib.sha256(pixels).hexdigest()})
    required = {'sole_straight_arrow_visible'}
    if occupied:
        required.add('participant_visible')
    if not required <= claims:
        raise ValueError('original pixel review omits required arrow or participant')
    return {'packet_sha256': sha(packet_path), 'observations': receipts,
            'visual_claims_are_reviewer_attestations': True}
