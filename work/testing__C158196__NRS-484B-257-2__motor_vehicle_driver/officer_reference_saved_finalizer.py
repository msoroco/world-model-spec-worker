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


def analyze(attempt, site_path=None, review_path=None):
    attempt = Path(attempt).resolve()
    capture_path = attempt / 'officer-reference-capture.json'
    config_path = attempt / 'config.json'
    frame_path = attempt / 'video_frames.jsonl'
    source_paths = [capture_path, config_path, frame_path,
                    attempt / 'trace.jsonl', attempt / 'capture/evidence.jsonl',
                    *(attempt / (name + '.mkv') for name in CAMERAS)]
    if any(not path.is_file() or not path.stat().st_size for path in source_paths):
        raise ValueError('Complete original Native source set required')
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
    mapping, trace, evidence = (_rows(frame_path), _rows(attempt / 'trace.jsonl'),
                                _rows(attempt / 'capture/evidence.jsonl'))
    rows = capture['rows']
    if not (len(mapping) == len(trace) == len(evidence) == len(rows) == 600):
        raise ValueError('Incomplete original Native frame join')
    for index, (source, frame, motion, event) in enumerate(
            zip(rows, mapping, trace, evidence)):
        fid, time_s = source['carla_frame'], source['time_s']
        if (frame.get('video_frame') != index or frame.get('carla_frame') != fid or
                abs(frame.get('time_s', -1) - time_s) > 1e-4 or
                motion.get('frame') != fid or
                ('time_s' in motion and abs(motion['time_s'] - time_s) > 1e-4) or
                event.get('original_frame') != fid or
                ('camera_frames' in frame and
                 frame['camera_frames'] != {name: fid for name in CAMERAS})):
            raise ValueError('Original Native trace, evidence or video frame differs')
        refs = source.get('camera_raw_sources')
        if (not isinstance(refs, dict) or set(refs) != set(CAMERAS) or
                any(refs[name].get('carla_frame') != fid or
                    refs[name].get('video_frame') != index or
                    refs[name].get('raw_source') !=
                    str(attempt / (name + '.mkv')) + '#frame-' + str(index)
                    for name in CAMERAS)):
            raise ValueError('Original four-camera source join differs')
    for name in CAMERAS:
        _probe(attempt / (name + '.mkv'))
    officer_review = None
    if review_path is not None:
        if suffix in REFERENCE_SUFFIXES:
            raise ValueError('Reference-only case has no officer review')
        from officer_saved_review import validate
        officer_review = validate(capture_path, review_path,
                                  {name: attempt / (name + '.mkv') for name in CAMERAS})
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
    result = analyze(args.attempt, args.site, args.review)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
