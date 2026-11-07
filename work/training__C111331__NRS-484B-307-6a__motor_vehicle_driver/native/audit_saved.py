"""Independently audit the C111331 synthetic signal/entry comparisons."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def audit():
    summary = json.loads((HERE / 'synthetic-saved-summary.json').read_text())
    if summary['physical_success_claimed'] or summary['original_pixels_verified'] or len(summary['rows']) != 8:
        raise ValueError('Synthetic proof scope differs')
    indexed = {(r['case'], r['candidate']): r for r in summary['rows']}
    if len(indexed) != 8:
        raise ValueError('Eight distinct saved rows required')
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        pair = []
        for case in ('reference', 'contrast'):
            folder = HERE / 'synthetic-saved' / case / candidate
            item = indexed[case, candidate]
            measured = json.loads((folder / 'measurement.json').read_text())
            native = rows(folder / 'native_samples.jsonl')
            video = rows(folder / 'video_frames.jsonl')
            if item['measurement_sha256'] != sha(folder / 'measurement.json') or item['native_sha256'] != sha(folder / 'native_samples.jsonl') or item['video_frames_sha256'] != sha(folder / 'video_frames.jsonl'):
                raise ValueError('Saved source hash differs')
            if len(native) != 480 or len(video) != 480 or item['negatives_rejected'] != ['missing_native_source', 'broken_camera_join', 'invalid_observed_phase']:
                raise ValueError('Saved 480-frame or negative proof differs')
            if measured['source_kind'] != 'synthetic_cpu_native_observation' or measured['physical_native_evidence'] or measured['original_pixel_visibility_verified'] or measured['statutory_verdict_claimed']:
                raise ValueError('Synthetic evidence promoted to physical or legal claim')
            if measured['sources'] != {'native_samples.jsonl': item['native_sha256'], 'video_frames.jsonl': item['video_frames_sha256']}:
                raise ValueError('Saved measurement source binding differs')
            first_entry = next(i for i, n in enumerate(native) if min(p[1] for p in n['native_body_xy_m']) <= 7)
            red = next(i for i, n in enumerate(native) if n['observed_signal_state'] == 'red')
            if first_entry != measured['observed_full_body_entry_frame'] or red != measured['observed_red_start_frame'] or measured['observed_signal_phase_at_entry'] != native[first_entry]['observed_signal_state']:
                raise ValueError('Independent signal at body entry differs')
            pair.append((native, video, measured))
        (r_native, r_video, r), (c_native, c_video, c) = pair
        if r['observed_signal_phase_at_entry'] != 'yellow' or c['observed_signal_phase_at_entry'] != 'red':
            raise ValueError('Yellow/red pair differs')
        if r['observed_full_body_entry_frame'] != c['observed_full_body_entry_frame'] or any(a['native_center_xy_m'] != b['native_center_xy_m'] or a['native_body_xy_m'] != b['native_body_xy_m'] for a, b in zip(r_native, c_native)):
            raise ValueError('Controlled movement trace differs')
        if r_video != c_video or r['observed_yellow_start_frame'] != c['observed_yellow_start_frame']:
            raise ValueError('Controlled frame or yellow onset differs')
        if not r['entry_to_red_margin_frames'] > 0 > c['entry_to_red_margin_frames']:
            raise ValueError('Controlled red timing margin differs')
    return {'passed': True, 'audited_bundles': 8, 'controlled_pairs': 4,
            'negative_rejections': 24, 'synthetic_only': True,
            'summary_sha256': sha(HERE / 'synthetic-saved-summary.json')}


if __name__ == '__main__':
    print(json.dumps(audit(), sort_keys=True))
