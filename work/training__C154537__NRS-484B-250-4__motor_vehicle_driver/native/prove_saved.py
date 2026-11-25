"""CPU original-shape diagnostic; fixtures cannot establish Native or legal facts."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(path, stop=True):
    path.mkdir()
    survey = {'source_kind': 'original_native', 'stop_line_present': False,
        'near_side_crosswalk_present': False, 'sidewalk_derived_crosswalk_reviewed': True,
        'signal_installed': True, 'signal_uncovered': True,
        'official_device_provenance_reviewed': True,
        'through_highway_provenance_reviewed': True,
        'signal_id': '701', 'ego_front_offset_m': 2.0,
        'intersection_entry_front_x_m': -6.0,
        'driver_view_samples': [
            {'native_frame': 1000 + frame, 'center_x_m': x,
             'other_actor_id': 9, 'approaching_traffic_visible': x >= -11,
             'rays': [{'clear': x >= -11,
                       'blockers': [] if x >= -11 else [{'label': 'building'}]}
                      for _ in range(9)]}
            for frame, x in ((100, -15), (110, -13), (120, -11), (130, -9))]}
    (path / 'scene-survey.json').write_text(json.dumps(survey) + '\n')
    with (path / 'native-motion.jsonl').open('w') as motion, (path / 'video_frames.jsonl').open('w') as frames:
        for index in range(600):
            x = (-35 + min(index, 130) * .2 + max(0, index - 220) * .2
                 if stop else -35 + index * .2)
            x = min(x, 35)
            previous = (-35 + min(max(0, index-1), 130) * .2 + max(0, index-1 - 220) * .2
                        if stop else -35 + max(0, index-1) * .2)
            speed = 4.0 if index == 0 else (0 if x == previous else 20 * (x - previous))
            native = 1000 + index
            motion.write(json.dumps({'native_frame': native, 'video_frame': index,
                'time_s': index / 20, 'ego_center_x_m': round(x, 6),
                'ego_front_x_m': round(x + 2, 6), 'ego_speed_mps': round(speed, 6),
                'signal_id': survey['signal_id'], 'signal_state': 'inoperative_dark'}) + '\n')
            frames.write(json.dumps({'native_frame': native, 'video_frame': index,
                'time_s': index / 20, 'camera_native_frames': {name: native for name in CAMERAS}}) + '\n')
    for name in CAMERAS:
        (path / (name + '.mkv')).write_bytes(('synthetic-placeholder-' + name).encode())


def run(script, attempt, result):
    return subprocess.run([sys.executable, str(script), '--attempt', str(attempt), '--output', str(result)],
                          text=True, capture_output=True)


def main():
    output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    output_root.mkdir(parents=True, exist_ok=True)
    script = HERE / 'measure_saved.py'
    from audit_pair import audit
    with tempfile.TemporaryDirectory(prefix='c154537-saved-', dir=output_root) as temp:
        base = Path(temp)
        halt = base / 'halt'; fixture(halt, True)
        halt_result = base / 'halt-result.json'; completed = run(script, halt, halt_result)
        if completed.returncode:
            raise ValueError(completed.stderr)
        result = json.loads(halt_result.read_text())
        if not result['complete_cessation_sample_before_entry'] or result['continuous_nearest_point_proven'] or result['legal_verdict_claimed']:
            raise ValueError('Halt measurement or legal limits differ')
        roll = base / 'roll'; fixture(roll, False)
        roll_result = base / 'roll-result.json'; rolling = run(script, roll, roll_result)
        if rolling.returncode or json.loads(roll_result.read_text())['complete_cessation_sample_before_entry']:
            raise ValueError('Rolling contrast not measured')
        pair = audit(halt, roll)
        if not pair['passed'] or pair['legal_verdict_claimed']:
            raise ValueError('Source pair audit differs')
        roll_survey_path = roll / 'scene-survey.json'
        roll_survey = json.loads(roll_survey_path.read_text())
        roll_survey['signal_id'] = 'another-head'
        roll_survey_path.write_text(json.dumps(roll_survey) + '\n')
        try:
            audit(halt, roll)
        except ValueError as exc:
            if 'Governing signal' not in str(exc):
                raise
        else:
            raise ValueError('Changed governing signal was not rejected')
        roll_survey['signal_id'] = json.loads((halt / 'scene-survey.json').read_text())['signal_id']
        roll_survey_path.write_text(json.dumps(roll_survey) + '\n')
        survey_path = halt / 'scene-survey.json'
        survey = json.loads(survey_path.read_text()); survey['near_side_crosswalk_present'] = True
        survey_path.write_text(json.dumps(survey) + '\n')
        wrong = run(script, halt, base / 'wrong.json')
        if wrong.returncode == 0 or 'stop-line and crosswalk absence not established' not in wrong.stderr:
            raise ValueError('Crosswalk presence was not rejected')
        survey['near_side_crosswalk_present'] = False; survey_path.write_text(json.dumps(survey) + '\n')
        survey['driver_view_samples'][0]['rays'][0]['blockers'] = []
        survey_path.write_text(json.dumps(survey) + '\n')
        bad_ray = run(script, halt, base / 'bad-ray.json')
        if bad_ray.returncode == 0 or 'driver-view rays incomplete' not in bad_ray.stderr:
            raise ValueError('Inconsistent original ray source was not rejected')
        survey['driver_view_samples'][0]['rays'][0]['blockers'] = [{'label': 'building'}]
        survey_path.write_text(json.dumps(survey) + '\n')
        (halt / 'native-motion.jsonl').unlink()
        missing = run(script, halt, base / 'missing.json')
        if missing.returncode == 0 or 'Missing required source: native-motion.jsonl' not in missing.stderr:
            raise ValueError('Missing original motion not rejected')
        print(json.dumps({'passed': True, 'measurer_sha256': sha(script),
            'halt_result_sha256': sha(halt_result), 'roll_result_sha256': sha(roll_result),
            'halt_sample_before_entry': True, 'rolling_sample_before_entry': False,
            'crosswalk_presence_rejected': True, 'missing_motion_rejected': True,
            'inconsistent_ray_rejected': True,
            'source_pair_audit_sha256': sha(HERE / 'audit_pair.py'),
            'changed_governing_signal_rejected': True,
            'fixture_media_are_synthetic_placeholders': True,
            'continuous_nearest_point_proven': False,
            'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
