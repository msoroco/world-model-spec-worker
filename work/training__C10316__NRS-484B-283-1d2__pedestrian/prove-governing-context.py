"""Source-provenance checks for countdown control; no physical acceptance claim."""
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from audit_governing_context import audit, sha


def rejected(folder, expected):
    try:
        audit(folder, require_native=True)
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'{expected}: {error}')
        return str(error)
    raise AssertionError('Unqualified governing control accepted')


def main():
    root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='governing-context-', dir=root) as scratch:
        folder = Path(scratch)
        road = folder / 'road.xodr'
        shutil.copyfile(HERE / 'native/road.xodr', road)
        context = {'source_kind': 'synthetic_scene_request',
                   'crosswalk_id': 'C10316-authored-alley-crosswalk',
                   'near_highway_edge_xy_m': [-3.5, -.65],
                   'highway_span_m': 7, 'crossing_forward_xy': [1, 0],
                   'authored_map_sha256': sha(road)}
        source = folder / 'countdown-context.json'
        source.write_text(json.dumps(context) + '\n')
        diagnostic = audit(folder)
        assert diagnostic['governing_device_source_verified'] is False
        negatives = {'synthetic_native_requirement': rejected(folder, 'Original Native')}
        context['source_kind'] = 'native_observation'
        context['display_source_kind'] = 'debug_draw_string'
        source.write_text(json.dumps(context) + '\n')
        negatives['debug_text'] = rejected(folder, 'Debug text')
        context['display_source_kind'] = 'physical_device_actor'
        source.write_text(json.dumps(context) + '\n')
        negatives['missing_samples'] = rejected(folder, 'Missing original countdown samples')
        (folder / 'countdown_samples.jsonl').write_text('')
        negatives['missing_independent_review'] = rejected(folder, 'Native countdown review missing source')
        (folder / 'countdown-original-review.json').write_text('{}\n')
        (folder / 'driver_reference.mkv').write_bytes(b'fixture-only')
        (folder / 'video_frames.jsonl').write_text('')
        (folder / 'capture').mkdir()
        (folder / 'capture/manifest.json').write_text(json.dumps({
            'synthetic_diagnostic': True, 'extraction_confirmed': True}) + '\n')
        negatives['synthetic_capture'] = rejected(folder, 'cannot use synthetic')
        context['source_kind'] = 'synthetic_scene_request'
        context['authored_map_sha256'] = '0' * 64
        source.write_text(json.dumps(context) + '\n')
        try:
            audit(folder)
        except ValueError as error:
            assert 'another crossing map' in str(error)
            negatives['changed_map'] = str(error)
        else:
            raise AssertionError('Changed authored map accepted')
    print(json.dumps({'passed': True, 'synthetic_diagnostic': diagnostic,
                      'negatives': negatives, 'native_device_proved': False}, sort_keys=True))


if __name__ == '__main__':
    main()
