"""Synthetic source fixtures and adversarial CPU checks for countdown timing."""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / 'native'))
from measure_countdown import measure
from signal_clock import frame_state


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(x, separators=(',', ':')) + '\n' for x in rows))


def case(folder, zero_time_s):
    folder.mkdir(parents=True)
    shutil.copyfile(HERE / 'native/road.xodr', folder / 'road.xodr')
    context = {
        'source_kind': 'synthetic_scene_request',
        'crosswalk_id': 'C10316-authored-alley-crosswalk',
        'device_id': 'C10316-authored-pedestrian-head-east',
        'device_governs_crosswalk': True, 'device_faces_pedestrian': True,
        'near_highway_edge_xy_m': [-3.5, -.65], 'crossing_forward_xy': [1, 0],
        'highway_span_m': 7.0,
        'highway_boundary_source': 'authored C10316 crosswalk and highway polygon request',
        'authored_map_sha256': sha(folder / 'road.xodr'),
        'exception_context': 'unverified synthetic request',
    }
    (folder / 'countdown-context.json').write_text(json.dumps(context, indent=2) + '\n')
    rows = []
    for i in range(240):
        time = round(i/20, 2)
        x = -4.5 + (8.14/8.0)*time
        y = -.65
        half = .12
        signal = frame_state(i, zero_time_s)
        assert signal['time_s'] == time
        displayed = signal['displayed_countdown_s']
        rows.append({
            'native_frame': 100+i, 'time_s': time,
            'crosswalk_id': context['crosswalk_id'], 'device_id': context['device_id'],
            'indication': signal['indication'],
            'display_illuminated': signal['display_illuminated'],
            'displayed_countdown_s': displayed,
            'pedestrian_xy_m': [x, y],
            'pedestrian_footprint_xy_m': [[x-half,y-half],[x+half,y-half],[x+half,y+half],[x-half,y+half]],
            'synthetic_diagnostic': True,
        })
    write_rows(folder / 'countdown_samples.jsonl', rows)
    return rows, context


def rejected(root, name, rows, context, expected):
    folder = root / name
    folder.mkdir()
    shutil.copyfile(HERE / 'native/road.xodr', folder / 'road.xodr')
    if rows is not None:
        write_rows(folder / 'countdown_samples.jsonl', rows)
    (folder / 'countdown-context.json').write_text(json.dumps(context) + '\n')
    try:
        measure(folder / 'countdown_samples.jsonl', folder / 'countdown-context.json')
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError(f'{name}: expected {expected!r}, got {error!r}')
        return {'name': name, 'error': str(error)}
    raise AssertionError(name + ': negative was accepted')


def main():
    root = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c10316-countdown-'))
    early_rows, early_context = case(root / 'probe_01', 10.0)
    late_rows, late_context = case(root / 'probe_02', 7.0)
    case(root / 'boundary_diagnostic', 8.0)
    early = measure(root / 'probe_01/countdown_samples.jsonl', root / 'probe_01/countdown-context.json')
    late = measure(root / 'probe_02/countdown_samples.jsonl', root / 'probe_02/countdown-context.json')
    boundary = measure(root / 'boundary_diagnostic/countdown_samples.jsonl', root / 'boundary_diagnostic/countdown-context.json')
    assert early['clearance_relative_to_displayed_zero'] == 'before_zero'
    assert late['clearance_relative_to_displayed_zero'] == 'at_or_after_zero'
    assert early['full_body_clearance'] == late['full_body_clearance']
    assert early['entry'] == late['entry']
    assert boundary['clearance_relative_to_displayed_zero'] == 'sampling_overlap_unresolved'
    assert early['exceptions_reviewed'] is False and late['legal_verdict_claimed'] is False
    negatives = []
    negatives.append(rejected(root, 'missing_samples', None, early_context, 'Missing required source'))
    broken = copy.deepcopy(early_rows); broken[20].pop('displayed_countdown_s')
    negatives.append(rejected(root, 'missing_display', broken, early_context, 'Legible original displayed countdown missing'))
    broken = copy.deepcopy(early_rows); broken[100]['indication'] = 'dont_walk_steady'
    negatives.append(rejected(root, 'not_flashing', broken, early_context, 'Flashing pedestrian indication missing'))
    broken = copy.deepcopy(early_rows)
    for row in broken: row['display_illuminated'] = True
    negatives.append(rejected(root, 'no_light_cycle', broken, early_context, 'Original flashing illumination cycle missing'))
    context = dict(early_context, device_governs_crosswalk=False)
    negatives.append(rejected(root, 'wrong_governance', early_rows, context, 'Governing pedestrian direction not established'))
    broken = copy.deepcopy(early_rows)
    for row in broken: row['displayed_countdown_s'] = 0
    negatives.append(rejected(root, 'unbracketed_zero', broken, early_context, 'Countdown zero transition not bracketed'))
    broken = copy.deepcopy(early_rows)
    for row in broken:
        delta = -4.5 + 5.0*row['time_s']/8.0 - row['pedestrian_xy_m'][0]
        row['pedestrian_xy_m'][0] += delta
        for vertex in row['pedestrian_footprint_xy_m']: vertex[0] += delta
    negatives.append(rejected(root, 'no_clearance', broken, early_context, 'Crossing entry, full clearance, or displayed zero missing'))
    context = dict(early_context, source_kind='native_observation')
    negatives.append(rejected(root, 'unproven_native', early_rows, context, 'Native countdown needs map, original pixel, and frame provenance'))
    summary = {'format': 'c10316-countdown-synthetic-measurement-v1', 'retained_root': str(root),
               'positive': {'probe_01': early, 'probe_02': late},
               'boundary_diagnostic': boundary, 'negatives': negatives,
               'scope': 'synthetic event timing only; no Native device, pixels, exception review or legal verdict'}
    (HERE / 'draft-countdown-measurement-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({'planned_probe_positives': 2, 'boundary_diagnostics': 1, 'negatives': len(negatives),
                      'probe_01': early['clearance_relative_to_displayed_zero'],
                      'probe_02': late['clearance_relative_to_displayed_zero'],
                      'same_pedestrian_motion': True, 'accepted_recordings': 0}))


if __name__ == '__main__':
    main()
