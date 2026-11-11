"""Saved-source measurement for NRS 484B.623(1); no legal classification."""
import argparse
import json
from pathlib import Path
from slow_speed import measure


def _rows(root, name):
    path = root / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not rows:
        raise ValueError('Empty required source: ' + name)
    return rows


def analyze(attempt):
    root = Path(attempt)
    frames = _rows(root, 'video_frames.jsonl')
    actors = _rows(root, 'participant_state.jsonl')
    props = _rows(root, 'prop_state.jsonl')
    context_path = root / 'slow_context.json'
    if not context_path.is_file():
        raise ValueError('Missing required source: slow_context.json')
    context = json.loads(context_path.read_text())
    if len(frames) != len(actors) or len(frames) != len(props):
        raise ValueError('source frame count differs')
    samples = []
    for f,a,p in zip(frames,actors,props):
        if f['carla_frame'] != a['frame'] or f['carla_frame'] != p['frame']:
            raise ValueError('original frame join differs')
        if abs(f['time_s']-a['time_s']) > 1e-5 or abs(f['time_s']-p['time_s']) > 1e-5:
            raise ValueError('original time join differs')
        sample = dict(a)
        sample['obstruction_visible'] = p.get('obstruction_visible')
        sample['control_visible'] = p.get('control_visible')
        sample['source'] = 'participant_state.jsonl'
        samples.append(sample)
    observations = measure(samples)
    if context.get('case_branch') not in ('flowing_reference','slow_with_following_traffic',
                                          'slow_for_obstruction','slow_under_control'):
        raise ValueError('missing exact case branch context')
    if context['case_branch']=='slow_for_obstruction' and not all(
            p.get('obstruction_present') is True for p in props):
        raise ValueError('physical obstruction missing from retained prop source')
    if context['case_branch']=='slow_under_control' and not all(
            p.get('control_present') is True for p in props):
        raise ValueError('physical control missing from retained prop source')
    return {'case_branch':context['case_branch'], 'measurements':observations,
            'source_files':['video_frames.jsonl','participant_state.jsonl',
                            'prop_state.jsonl','slow_context.json'],
            'physical_acceptance_claimed':False,'legal_judgment':'unresolved'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=analyze(args.attempt)
    Path(args.output).write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__': main()
