"""Saved-only C158190 observations from reviewed original capture sources."""

import argparse
import hashlib
import json
from pathlib import Path

from yield_context import CAMERAS, derive_context
from yield_controller import PREFIX, Stage
from yield_measurements import analyze


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain prior C158190 finalization; choose a fresh attempt')
    required = ('config.json', 'road.xodr', 'road_context.json',
                'control_inventory.jsonl', 'approach_history.jsonl',
                'interaction_history.jsonl', 'control_context.json',
                'visibility_rays.jsonl', 'visibility_samples.json',
                'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                'capture/native_map_facts.json', 'rendered_marking_review.json', *CAMERAS)
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config.get('selected_case_id')
    stage = Stage(case_id)
    if not case_id.startswith(PREFIX):
        raise ValueError('Wrong exact C158190 case')
    context = derive_context(attempt)
    report = analyze(attempt, reviewed_context=context)
    history = _rows(attempt / 'approach_history.jsonl')
    rays = _rows(attempt / 'visibility_rays.jsonl')
    by_frame = {row['frame']: row for row in rays}
    if len(history) != len(rays) or len(by_frame) != len(rays):
        raise ValueError('Approach and original sight rays differ')
    channels = attempt / 'channels'
    channels.mkdir()
    values = {'ego_approach_speed': [row['ego_speed_mps'] for row in history],
              'through_highway_sight_clear': [int(by_frame[row['frame']]['clear'])
                                              for row in history]}
    for name, numbers in values.items():
        with (channels / (name + '.jsonl')).open('x') as stream:
            for row, number in zip(history, numbers):
                stream.write(json.dumps({'original_frame': row['frame'],
                                         'time_s': row['time_s'], 'value': number},
                                        allow_nan=False) + '\n')
    site_review = {'yield_site_review': {
        'authored_site_sha256': context['authored_site_sha256'],
        'source_review_sha256': context['source_review_sha256'],
        'native_yield_sign_id': context['native_yield_sign_id'],
        'native_map_id': context['native_map_id'],
        'review_scope': 'original camera frames named in rendered_marking_review.json',
        'physical_acceptance': False}}
    (channels / 'yield_site_review.json').write_text(json.dumps(site_review, indent=2) + '\n')
    measured = report['speed_at_closest_view_mps']
    requested = (stage.approach_speed_mps if case_id.endswith('__yield_nearest_view_no_slow')
                 else stage.clear_speed_mps if case_id.endswith('__yield_nearest_view_clear')
                 else stage.view_speed_mps)
    target = {'target': 'sampled_ego_speed_at_closest_sourced_through_road_view_mps',
              'requested': requested, 'measured': measured,
              'method': 'original ego velocity at closest sampled clear through-road ray',
              'tolerance': 1.0, 'matched': abs(requested - measured) <= 1.0,
              'physical_cause_confirmed': False,
              'cause_evidence': ['approach_history.jsonl', 'visibility_rays.jsonl',
                                 'video_frames.jsonl', 'rendered_marking_review.json']}
    evidence = [{'name': name, 'unit': ('m/s' if name == 'ego_approach_speed' else 'count'),
                 'reference': 'channels/' + name + '.jsonl'} for name in values]
    evidence.append({'name': 'yield_site_review', 'unit': 'structured record',
                     'reference': 'channels/yield_site_review.json'})
    result = {'case_id': case_id,
              'measured_values': {'speed_at_closest_view_mps': measured,
                                  'closest_sourced_visible_sample': report['closest_sourced_visible_sample'],
                                  'minimum_observed_approach_speed_mps': report['minimum_observed_approach_speed_mps']},
              'target_checks': [target],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'saved source analysis; independent physical audit pending',
              'physical_failure_flags': ['actual sign face, full marking absence, human view, immediate hazard and yielding remain physical/legal review'],
              'trace_reference': 'trace.jsonl',
              'video_references': list(CAMERAS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence,
              'source_evidence_hashes': {**report['sources'],
                                         'road.xodr': _sha(attempt/'road.xodr'),
                                         'control_inventory.jsonl': _sha(attempt/'control_inventory.jsonl'),
                                         'interaction_history.jsonl': _sha(attempt/'interaction_history.jsonl'),
                                         'control_context.json': _sha(attempt/'control_context.json'),
                                         'rendered_marking_review.json': _sha(attempt/'rendered_marking_review.json')},
              'capture_evidence_sha256': _sha(attempt/'capture/evidence.jsonl'),
              'realized_observables': {}}
    try:
        from worker_exchange.native_output import physical_result, write_result
    except ModuleNotFoundError:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
                               'runtime/scenario_pipeline'))
        from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    analysis = {'format': 'worker-c158190-yield-analysis', 'case_id': case_id,
                'measurements': {'speed_at_closest_view_mps': {
                    'value': measured, 'method': target['method'],
                    'sources': result['source_evidence_hashes']}},
                'legal_conclusion': 'unresolved', 'source_report': report,
                'source_review_sha256': context['source_review_sha256']}
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(Path(args.attempt), Path(args.output))


if __name__ == '__main__':
    main()
