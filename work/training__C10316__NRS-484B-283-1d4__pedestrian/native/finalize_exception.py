"""Source-bound countdown timing report; no legal verdict or acceptance claim."""
import argparse
import json
import math
from pathlib import Path
import subprocess

from exception import measure, sha


def required(folder, name):
    path = Path(folder) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def rows(folder, name):
    return [json.loads(line) for line in required(folder, name).read_text().splitlines() if line.strip()]


def verify_original_joins(folder, count):
    names = ('trace.jsonl', 'capture/evidence.jsonl', 'video_frames.jsonl',
             'exception-samples.jsonl', 'capture/native/frames.jsonl')
    trace, evidence, mapping, samples, native = (rows(folder, name) for name in names)
    if any(len(source) != count for source in (trace, evidence, mapping, samples, native)):
        raise ValueError('Original prior-entry trace/evidence/Native/frame counts differ')
    previous_frame, previous_time = -1, -math.inf
    for index, (t, e, m, s, n) in enumerate(zip(trace, evidence, mapping, samples, native)):
        frame, time = m.get('native_frame'), m.get('time_s')
        if type(frame) is not int or type(time) not in (int, float) or frame <= previous_frame or time <= previous_time:
            raise ValueError('Original prior-entry frame/time order invalid')
        if m.get('video_frame') != index or m.get('carla_frame') != frame:
            raise ValueError('Original prior-entry camera frame mapping invalid')
        if any(value != frame for value in (t.get('frame'), e.get('original_frame'),
                                             s.get('native_frame'), n.get('frame'))):
            raise ValueError('Original prior-entry Native frame join differs')
        if any(abs(float(value) - time) > 1e-4 for value in
               (t['time_s'], e['recording_time_s'], s['time_s'])):
            raise ValueError('Original prior-entry timestamp join differs')
        evidence_body = {(round(v[0], 3), round(v[1], 3)) for v in e['ego']['body_vertices_m']}
        sample_body = {(round(v[0], 3), round(v[1], 3)) for v in s['pedestrian_footprint_xy_m']}
        if len(evidence_body) != 4 or evidence_body != sample_body:
            raise ValueError('Original prior-entry pedestrian footprint differs')
        previous_frame, previous_time = frame, time
    capture = json.loads(required(folder, 'capture/manifest.json').read_text())
    if capture.get('extraction_confirmed') is not True or capture.get('frames') != count:
        raise ValueError('Original prior-entry capture extraction incomplete')
    return {'frames': count, 'first_frame': mapping[0]['native_frame'],
            'last_frame': mapping[-1]['native_frame'],
            'source_hashes': {name: sha(Path(folder) / name) for name in names}}


def video_info(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing required source: ' + path.name)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
                            '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json',
                            str(path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    if probe.returncode:
        raise ValueError('Source prior-entry video decode failed: ' + path.name)
    streams = json.loads(probe.stdout).get('streams', [])
    if len(streams) != 1 or not str(streams[0].get('nb_read_frames', '')).isdigit():
        raise ValueError('Source prior-entry video frame count missing: ' + path.name)
    return int(streams[0]['nb_read_frames']), int(streams[0]['width']), int(streams[0]['height'])


def prior_entry_exception(folder):
    folder = Path(folder)
    return measure(folder / 'exception-samples.jsonl', folder / 'exception-context.json')


def report(folder, case_id):
    folder = Path(folder)
    value = prior_entry_exception(folder)
    sources = {name: sha(folder / name) for name in ('exception-samples.jsonl', 'exception-context.json', 'road.xodr')}
    return {'format': 'worker-analysis-report-v1', 'case_id': case_id,
            'measurements': {'prior_entry_exception_source_facts': {
                'method': 'prior_entry_exception', 'value': value, 'sources': sources}},
            'scope': 'prior-entry source facts without lawful-entry, exception or legal verdict'}


def finalize(attempt, output):
    from worker_exchange.native_output import validate_result
    attempt, output = Path(attempt).resolve(), Path(output).resolve()
    if output.exists() or (attempt / 'result.json').exists():
        raise ValueError('Retain original steady finalization; use a fresh attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    count = config['duration_s'] * config['rate_hz']
    if count != 240:
        raise ValueError('Full 12-second steady window changed')
    joins = verify_original_joins(attempt, count)
    analysis = report(attempt, config['case_id'])
    measured = analysis['measurements']['prior_entry_exception_source_facts']['value']
    context = json.loads(required(attempt, 'exception-context.json').read_text())
    expected = 'dont_walk_flashing' if config['case_suffix'] == 'exception_1_1' else 'walk'
    videos = {}
    for camera in config['cameras']:
        name = camera['name'] + '.mkv'
        info = video_info(attempt / name)
        if info != (count, camera['width'], camera['height']):
            raise ValueError('Source prior-entry camera frame count or dimensions differ: ' + name)
        videos[name] = {'frames': info[0], 'width': info[1], 'height': info[2]}
    evidence = []
    for channel in config['recording_description']['channels']:
        ref = 'channels/' + channel['name'] + '.jsonl'
        required(attempt, ref)
        evidence.append({'name': channel['name'], 'unit': channel['unit'], 'reference': ref})
    for item in config['recording_description']['context_inputs']:
        evidence.append({'name': item['name'], 'unit': item['unit'],
                         'reference': 'exception-context.json'})
    relation = measured['entry_indication']
    native = context['source_kind'] == 'native_observation'
    result = {'case_id': config['case_id'],
              'measured_values': {'entry_indication': relation,
                                  'first_entry': measured['first_entry'],
                                  'full_body_clearance': measured['full_body_clearance'],
                                  'steady_start': measured['steady_start'],
                                  'post_steady_crossing_samples': measured['post_steady_crossing_samples'],
                                  'continued_progress_source_fact': measured['continued_progress_source_fact'],
                                  'lawful_prior_entry_proven': False},
              'target_checks': [{'target': 'source-bound prior-entry indication before steady',
                  'requested': expected, 'measured': relation,
                  'method': 'original joined steady source and full pedestrian footprint',
                  'tolerance': 0, 'matched': relation == expected,
                  'physical_cause_confirmed': False,
                  'cause_evidence': ['exception-samples.jsonl', 'exception-context.json', 'trace.jsonl']}],
              'setup_confirmed': False, 'behavior_attempted': native,
              'maneuver_completed': native and relation == expected,
              'termination_reason': 'full original source interval retained',
              'physical_failure_flags': ['physical_signal_governance_pixels_highway_and_exceptions_unverified'],
              'trace_reference': 'trace.jsonl', 'video_references': list(videos),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence,
              'realized_observables': {'prior_entry_to_steady_margin_s': {
                  'value': measured['steady_start']['time_interval_s'][1] - measured['first_entry']['time_interval_s'][1],
                  'unit': 's',
                  'method': 'original synchronized event brackets',
                  'time_window': 'entire original 12-second capture',
                  'statistic': 'first full-body entry versus first steady indication',
                  'reference': 'exception-samples.jsonl'}},
              'provenance_kind': 'synthetic_local_diagnostic' if not native else 'native_source_shape_unverified',
              'accepted': False, 'legal_verdict_claimed': False}
    validate_result(result)
    analysis.update(format='c10316-saved-prior-entry-analysis-v1', candidate_id=config['candidate_id'],
                    original_joins=joins, video_frames=videos,
                    scope='saved source joins and video decode; no physical signal or legal finding')
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case-id')
    args = parser.parse_args()
    if not (args.attempt / 'config.json').is_file():
        if not args.case_id:
            raise ValueError('Source-only analysis requires --case-id')
        data = report(args.attempt, args.case_id)
        args.output.write_text(json.dumps(data, indent=2) + '\n')
    else:
        data = finalize(args.attempt, args.output)
    print(json.dumps({'case_id': data['case_id'], 'entry_indication':
                      data['measurements']['prior_entry_exception_source_facts']['value']['entry_indication'],
                      'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
