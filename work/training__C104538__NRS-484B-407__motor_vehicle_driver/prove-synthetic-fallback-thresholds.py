"""Exercise C104538 saved-source thresholds on explicitly synthetic rows."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from measure_native import analyze


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, sort_keys=True, indent=2) + '\n')


def main():
    original = REPO / '.runtime-work/c104538/full-saved-v2/below_500_ft/positive'
    if not (original / 'config.json').is_file():
        raise ValueError('Build the 480-frame saved fixture first')
    output = REPO / '.runtime-work/c104538/fallback-thresholds-v1'
    if output.exists():
        shutil.rmtree(output)
    names = ('config.json', 'native-construction-context.json', 'native_road_readback.xodr',
             'trace.jsonl', 'capture/evidence.jsonl', 'native_body_history.jsonl',
             'driver_eye_rays.jsonl', 'video_frames.jsonl')
    cases = {}
    for label in ('baseline', 'crest_error', 'barrier_gap', 'source_corrupt'):
        target = output / label
        target.mkdir(parents=True)
        for name in names:
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(original / name, destination)
        context_path = target / 'native-construction-context.json'
        context = json.loads(context_path.read_text())
        if label == 'crest_error':
            context['waypoint_elevation_samples'][1]['native_waypoint_z_m'] = 3.40
            write(context_path, context)
        if label == 'barrier_gap':
            second = context['barrier_inventory'][1]
            second['requested']['native_xyz_m'][0] += .10
            for vertex in second['world_vertices_m']:
                vertex[0] += .10
            write(context_path, context)
        if label == 'source_corrupt':
            (target / 'native_road_readback.xodr').write_text('damaged synthetic map\n')
            try:
                analyze(target)
            except ValueError as exc:
                if 'Native map readback hash differs' not in str(exc):
                    raise
                cases[label] = {'rejected': True, 'error': str(exc)}
                continue
            raise AssertionError('Changed Native map source was accepted')
        measurement = analyze(target)
        assert measurement['original_frames'] == 480
        assert measurement['accepted'] is False
        assert measurement['original_pixel_visibility_proven'] is False
        expected = (label == 'crest_error', label == 'barrier_gap')
        observed = (measurement['fallback1_trigger_measured'],
                    measurement['fallback2_trigger_measured'])
        assert observed == expected, (label, observed)
        cases[label] = {
            'maximum_native_crest_height_error_m': measurement['maximum_native_crest_height_error_m'],
            'maximum_native_barrier_box_gap_m': measurement['maximum_native_barrier_box_gap_m'],
            'fallback1_trigger': observed[0], 'fallback2_trigger': observed[1],
            'fallback3_original_pixel_trigger': measurement['fallback3_original_pixel_trigger_measured'],
            'context_sha256': digest(context_path),
            'map_sha256': digest(target / 'native_road_readback.xodr')}
    receipt = {'format': 'c104538-synthetic-saved-trigger-threshold-v1',
               'source_kind': 'synthetic_cpu_fixture', 'source_dir': str(output.relative_to(REPO)),
               'cases': cases, 'original_native_observed': False,
               'original_pixel_observed': False, 'selected': False}
    write(HERE / 'synthetic-fallback-threshold-summary.json', receipt)
    print(json.dumps({'baseline': cases['baseline'], 'crest_error': cases['crest_error'],
                      'barrier_gap': cases['barrier_gap'], 'source_corrupt': cases['source_corrupt']}))


if __name__ == '__main__':
    main()
