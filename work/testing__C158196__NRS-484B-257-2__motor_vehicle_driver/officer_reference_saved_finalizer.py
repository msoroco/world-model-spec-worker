"""Validate original officer/reference sources and retain unresolved judgments."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from officer_capture_step import CAMERAS
from officer_direction import REFERENCE_SUFFIXES, behavior_suffix
from officer_reference_plan import SITES
from reference_saved_measure import measure


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def _probe(path):
    probe = subprocess.run(
        ['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0',
         '-show_entries', 'stream=codec_name,nb_read_frames', '-of', 'json', str(path)],
        capture_output=True, text=True, check=True)
    streams = json.loads(probe.stdout).get('streams', [])
    if (len(streams) != 1 or streams[0].get('codec_name') != 'ffv1' or
            streams[0].get('nb_read_frames') != '600'):
        raise ValueError('Original FFV1 camera source lacks 600 frames')


def measure_reference_stop(report):
    sample = report['reference_measurement']['first_engineering_stop_before_reference']
    return {'observed': sample is not None, 'first_sample': sample,
            'reference_kind': report['reference_measurement']['reference_kind'],
            'overshot_before_stop':
            report['reference_measurement']['overshot_before_engineering_stop']}


def measure_police_control(report):
    review = report['officer_original_frame_review']
    if review is None:
        raise ValueError('Independent original-frame officer review required')
    return review['police_control_verified']


def analyze(attempt, site_path=None, review_path=None):
    attempt = Path(attempt).resolve()
    capture_path = attempt / 'officer-reference-capture.json'
    config_path = attempt / 'config.json'
    frame_path = attempt / 'video_frames.jsonl'
    history_path = attempt / 'officer_reference_history.jsonl'
    source_paths = [capture_path, config_path, frame_path, history_path,
                    attempt / 'trace.jsonl', attempt / 'capture/evidence.jsonl',
                    *(attempt / (name + '.mkv') for name in CAMERAS)]
    for path in source_paths:
        if not path.is_file() or not path.stat().st_size:
            raise ValueError('Missing required source: ' + str(path.relative_to(attempt)))
    config = json.loads(config_path.read_text())
    capture = json.loads(capture_path.read_text())
    case_id = config.get('selected_case_id')
    suffix = behavior_suffix(case_id)
    site_path = Path(site_path).resolve() if site_path is not None else attempt / SITES[suffix][0]
    if (capture.get('case_id') != case_id or
            (config.get('law_id'), config.get('cell_id'), config.get('actor')) !=
            ('NRS-484B-257-2', 'C158196', 'motor_vehicle_driver') or
            site_path.name != SITES[suffix][0]):
        raise ValueError('Exact case, law, actor or authored site differs')
    measured = measure(capture_path, site_path)
    mapping, history, trace, evidence = (_rows(frame_path), _rows(history_path),
                                        _rows(attempt / 'trace.jsonl'),
                                _rows(attempt / 'capture/evidence.jsonl'))
    rows = capture['rows']
    if not (len(mapping) == len(history) == len(trace) == len(evidence) ==
            len(rows) == 600):
        raise ValueError('Incomplete original Native frame join')
    for index, (source, frame, body, motion, event) in enumerate(
            zip(rows, mapping, history, trace, evidence)):
        fid, time_s = source['carla_frame'], source['time_s']
        if (frame.get('video_frame') != index or frame.get('carla_frame') != fid or
                abs(frame.get('time_s', -1) - time_s) > 1e-4 or
                motion.get('frame') != fid or
                ('time_s' in motion and abs(motion['time_s'] - time_s) > 1e-4) or
                event.get('original_frame') != fid or
                ('camera_frames' in frame and
                 frame['camera_frames'] != {name: fid for name in CAMERAS}) or
                body.get('frame') != fid or
                abs(body.get('time_s', -1) - time_s) > 1e-4 or
                body.get('ego_body_vertices_xy_m') != source['ego_body_vertices_xy_m'] or
                body.get('ego_speed_mps') != source['ego_speed_mps']):
            raise ValueError('Original Native trace, evidence or video frame differs')
        refs = source.get('camera_raw_sources')
        if (not isinstance(refs, dict) or set(refs) != set(CAMERAS) or
                any(refs[name].get('carla_frame') != fid or
                    refs[name].get('video_frame') != index or
                    refs[name].get('raw_source') not in (
                        name + '.mkv#frame-' + str(index),
                        str(attempt / (name + '.mkv')) + '#frame-' + str(index))
                    for name in CAMERAS)):
            raise ValueError('Original four-camera source join differs')
    for name in CAMERAS:
        _probe(attempt / (name + '.mkv'))
    officer_review = None
    if review_path is None and (attempt / 'officer-original-frame-review.json').is_file():
        review_path = attempt / 'officer-original-frame-review.json'
    if review_path is not None:
        review_path = Path(review_path).resolve()
        if review_path != attempt / 'officer-original-frame-review.json':
            raise ValueError('Independent officer review must be retained in attempt')
        if suffix in REFERENCE_SUFFIXES:
            raise ValueError('Reference-only case has no officer review')
        from officer_saved_review import validate
        officer_review = validate(capture_path, review_path,
                                  {name: attempt / (name + '.mkv') for name in CAMERAS})
        source_paths.append(review_path)
    hashes = {str(path.relative_to(attempt)): _sha(path) for path in source_paths}
    return {'format': 'worker-subsection-2-officer-reference-saved-analysis',
            'case_id': case_id, 'source_sha256': hashes,
            'reference_measurement': measured,
            'officer_original_frame_review': officer_review,
            'physical_visibility_judgment': 'unreviewed',
            'police_authority_judgment': 'unreviewed' if officer_review is None
                                        else 'independent_review_retained',
            'legal_exception_judgment': 'unresolved',
            'physical_cause_confirmed': False}


def finalize(attempt, output, site_path=None, review_path=None):
    """Write derived channels and Native result after all original joins pass."""
    attempt, output = Path(attempt).resolve(), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Choose a fresh attempt; original and derived sources are immutable')
    report = analyze(attempt, site_path, review_path)
    config = json.loads((attempt / 'config.json').read_text())
    capture = json.loads((attempt / 'officer-reference-capture.json').read_text())
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    channel_path = channel_dir / 'ego_body_front_at_reference.jsonl'
    with channel_path.open('x') as stream:
        for row in capture['rows']:
            stream.write(json.dumps({
                'original_frame': row['carla_frame'], 'time_s': row['time_s'],
                'value': row['ego_front_x_m']}, allow_nan=False) + '\n')
    stopped = report['reference_measurement']['first_engineering_stop_before_reference']
    checks = [{'target': 'engineering_stop_before_authored_reference',
               'requested': True, 'measured': stopped is not None,
               'method': 'original complete body and speed joined to authored site',
               'tolerance': 0, 'matched': stopped is not None,
               'physical_cause_confirmed': False,
               'cause_evidence': ['officer-reference-capture.json',
                                  'officer_reference_history.jsonl',
                                  'video_frames.jsonl']}]
    suffix = behavior_suffix(report['case_id'])
    if suffix not in REFERENCE_SUFFIXES:
        review = report['officer_original_frame_review']
        verified = None if review is None else review['police_control_verified']
        checks.append({'target': 'observed_police_officer_control',
                       'requested': suffix != 'officer_present_inactive',
                       'measured': verified,
                       'method': 'independent original-frame officer review',
                       'tolerance': 0, 'matched': verified is not None and
                       verified == (suffix != 'officer_present_inactive'),
                       'physical_cause_confirmed': False,
                       'cause_evidence': [] if review_path is None else
                       ['officer-reference-capture.json', str(review_path)]})
    native = {'case_id': report['case_id'],
              'measured_values': report['reference_measurement'],
              'target_checks': checks, 'setup_confirmed': False,
              'behavior_attempted': False, 'maneuver_completed': False,
              'termination_reason': 'Original source review remains open',
              'physical_failure_flags': [
                  'Original officer authority, legal stop and visibility unresolved'],
              'trace_reference': 'trace.jsonl',
              'video_references': [name + '.mkv' for name in CAMERAS],
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['case']['recording_description'],
              'recording_evidence': [
                  {'name': 'ego_body_front_at_reference', 'unit': 'm',
                   'reference': 'channels/ego_body_front_at_reference.jsonl'}],
              'source_evidence_hashes': report['source_sha256'],
              'realized_observables': {}}
    from worker_exchange.native_output import physical_result, write_result
    native = physical_result(attempt, native)
    write_result(attempt, native)
    report['physical_checks'] = native['physical_checks']
    ref_inputs = ('officer-reference-capture.json',
                  'officer_reference_history.jsonl', 'video_frames.jsonl')
    measurements = {'first_engineering_stop_before_reference': {
        'value': measure_reference_stop(report), 'method': 'measure_reference_stop',
        'sources': {name: report['source_sha256'][name] for name in ref_inputs}}}
    if report['officer_original_frame_review'] is not None:
        officer_inputs = ('officer-reference-capture.json',
                          'officer-original-frame-review.json',
                          *(name + '.mkv' for name in CAMERAS))
        measurements['police_control_verified'] = {
            'value': measure_police_control(report),
            'method': 'measure_police_control',
            'sources': {name: report['source_sha256'][name] for name in officer_inputs}}
    report['measurements'] = measurements
    report['analysis_complete'] = True
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--site')
    parser.add_argument('--output', required=True)
    parser.add_argument('--review')
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Choose fresh analysis output')
    finalize(args.attempt, output, args.site, args.review)


if __name__ == '__main__':
    main()
