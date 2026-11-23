"""Independent source binding for the C229597 saved review context.

This audits software evidence integrity, not statutory exhibition or highway status.
"""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def probe(path):
    completed = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=nb_read_frames,r_frame_rate,width,height',
         '-of', 'json', str(path)], capture_output=True, text=True, check=True)
    streams = json.loads(completed.stdout)['streams']
    if len(streams) != 1:
        raise ValueError('One video stream required: ' + path.name)
    return streams[0]


def audit(attempt):
    attempt = Path(attempt)
    result = json.loads((attempt / 'result.json').read_text())
    report = json.loads((attempt / 'analysis-report.json').read_text())
    context = json.loads((attempt / 'channels/exhibition_episode_context.json').read_text())['exhibition_episode_context']
    highway = json.loads((attempt / 'channels/original_highway_survey.json').read_text())['original_highway_survey']
    provenance = json.loads((attempt / 'acquisition-provenance.json').read_text())
    config = json.loads((attempt / 'config.json').read_text())
    if not (result['case_id'] == report['case_id'] == provenance['case_id'] == config['case_id']):
        raise ValueError('Saved case identity differs')
    if result.get('accepted') or result.get('legal_verdict_claimed') or report.get('legal_verdict_claimed'):
        raise ValueError('Diagnostic source claims acceptance or legal verdict')
    if context.get('exhibition_review') != 'unresolved' or highway.get('highway_classification') != 'unresolved':
        raise ValueError('Unreviewed statutory judgment was assigned')
    if highway.get('jurisdiction_source') is not None:
        raise ValueError('Unreviewed jurisdiction source was assigned')
    bindings = {
        'trace.jsonl': context['trace_sha256'],
        'video_frames.jsonl': context['frame_map_sha256'],
        'road.xodr': highway['road_xodr_sha256'],
    }
    for view in VIEWS:
        bindings[view + '.mkv'] = context['camera_views'][view]
    for name, expected in bindings.items():
        if sha(attempt / name) != expected:
            raise ValueError('Review source hash differs: ' + name)
    frame_map = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    if len(frame_map) != FRAMES or len(trace) != FRAMES:
        raise ValueError('Incomplete review source interval')
    for index, (frame, motion) in enumerate(zip(frame_map, trace)):
        if (frame['video_frame'] != index or motion['video_frame'] != index
                or frame['carla_frame'] != motion['frame']
                or abs(frame['time_s'] - index / 20) > 1e-6
                or abs(motion['time_s'] - index / 20) > 1e-6):
            raise ValueError('Review frame join differs')
    for view in VIEWS:
        stream = probe(attempt / (view + '.mkv'))
        if (int(stream['nb_read_frames']) != FRAMES
                or stream['r_frame_rate'] != '20/1'
                or stream['width'] != (1920 if view == 'overview' else 1280)
                or stream['height'] != (1080 if view == 'overview' else 720)):
            raise ValueError('Review camera decode contract differs: ' + view)
    return {'format': 'c229597-saved-review-source-audit-v1',
            'case_id': result['case_id'], 'source_sha256': bindings,
            'decoded_frames_per_camera': FRAMES,
            'review_source_integrity_passed': True,
            'highway_classification': 'unresolved',
            'exhibition_review': 'unresolved',
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt), sort_keys=True))
