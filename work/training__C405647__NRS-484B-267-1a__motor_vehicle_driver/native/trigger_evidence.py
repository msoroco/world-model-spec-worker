"""Measured fallback decisions for unselected C405647 construction requests."""
import hashlib
import json
from pathlib import Path

from candidates import CANDIDATES

LAW_SHA256 = '05acca6d9cdbea0707963bae635458009d558500a8d40a96ce4fa9d8ca5a8d86'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _motion(folder):
    folder = Path(folder)
    scope = json.loads((folder / 'source-scope.json').read_text())
    if scope.get('assignment_law_text_sha256') != LAW_SHA256:
        raise ValueError('Fallback law source differs')
    case = scope.get('case_suffix')
    if case not in ('witness_1', 'witness_2'):
        raise ValueError('Fallback case differs')
    rows = [json.loads(line) for line in (folder / 'actor-frames.jsonl').read_text().splitlines()]
    if len(rows) != 480 or any(row['frame'] != i or abs(row['time_s'] - i / 20) > 1e-5
                               for i, row in enumerate(rows)):
        raise ValueError('Fallback frame/time source differs')
    if any(row.get('source_kind') not in ('synthetic_cpu', 'original_native') for row in rows):
        raise ValueError('Fallback provenance differs')
    gaps = [float(row['subject']['x_m']) - float(row['approach']['x_m']) for row in rows]
    clear = [float(row['subject']['y_m']) + .9 < -3.5 for row in rows]
    catchup = next((i for i, gap in enumerate(gaps) if gap <= 4.5), None)
    first_clear = next((i for i, yes in enumerate(clear) if yes), None)
    return case, catchup, first_clear, rows, {
        'source-scope.json': _sha(folder / 'source-scope.json'),
        'actor-frames.jsonl': _sha(folder / 'actor-frames.jsonl')}


def decide(candidate, folder, *, visibility_packet=None, source_video_path=None):
    if candidate not in CANDIDATES[1:]:
        raise ValueError('Expected one fallback candidate')
    case, catchup, first_clear, rows, sources = _motion(folder)
    if candidate == 'fallback1':
        # Clearance criterion is a trajectory/capture target, not a legal
        # determination of yielding or immediate approach.
        triggered = (first_clear is None or catchup is None or first_clear >= catchup
                     if case == 'witness_1' else
                     first_clear is not None and (catchup is None or first_clear < catchup))
        metric = {'first_full_body_clearance_frame': first_clear,
                  'catchup_frame': catchup, 'requested_case': case}
    elif candidate == 'fallback2':
        # Reserve the last six seconds for observing passage and aftermath.
        # Frame 360 is an engineering capture-window bound, not a legal bound.
        triggered = catchup is None or catchup >= 360
        metric = {'catchup_frame': catchup, 'latest_capture_target_frame': 359}
    else:
        if visibility_packet is None or source_video_path is None:
            raise ValueError('Pixel visibility packet or source video missing')
        packet_path = Path(visibility_packet)
        packet = json.loads(packet_path.read_text())
        video_path = Path(source_video_path)
        if not video_path.is_file():
            raise ValueError('Pixel source video missing')
        source_video_sha256 = _sha(video_path)
        if packet.get('source_video_sha256') != source_video_sha256:
            raise ValueError('Pixel source hash differs')
        if packet.get('source_kind') not in ('synthetic_cpu', 'original_pixel_review'):
            raise ValueError('Pixel review provenance invalid')
        total = packet.get('inspected_frame_count')
        visible = packet.get('front_red_lamp_visible_frame_count')
        if (not isinstance(total, int) or not isinstance(visible, int) or
                total <= 0 or visible < 0 or visible > total):
            raise ValueError('Original-pixel visibility counts invalid')
        # A capture-framing target only. A visible red pixel does not prove
        # statutory equipment compliance or authorization.
        triggered = visible * 4 < total * 3
        metric = {'front_red_lamp_visible_frame_count': visible,
                  'inspected_frame_count': total, 'capture_visibility_target_fraction': .75}
        sources['visibility_packet'] = _sha(packet_path)
        sources['source_video_sha256'] = source_video_sha256
    return {'case_suffix': case, 'candidate_id': candidate, 'triggered': bool(triggered),
            'metric': metric, 'sources': sources, 'legal_threshold_claimed': False,
            'source_rows_marked_original_native': all(
                row['source_kind'] == 'original_native' for row in rows),
            'physical_observation_verified': False}
