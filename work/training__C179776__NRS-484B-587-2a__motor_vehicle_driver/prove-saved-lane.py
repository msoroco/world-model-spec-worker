"""Source-shaped saved-only meter tests, without fabricated video acceptance."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('finalize_lane', ROOT / 'finalize_lane.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
comparison_spec = importlib.util.spec_from_file_location('comparison_audit', ROOT / 'comparison_audit.py')
comparison = importlib.util.module_from_spec(comparison_spec)
comparison_spec.loader.exec_module(comparison)
SCRATCH = ROOT.parent.parent / '.runtime-work' / 'c179776-saved-fixtures'
SCRATCH.mkdir(parents=True, exist_ok=True)
ASSIGNMENT = 'training__C179776__NRS-484B-587-2a__motor_vehicle_driver'


def write_lines(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def make(folder, suffix, shoulder):
    case = ASSIGNMENT + '__' + suffix
    (folder / 'designation-source.json').write_text(json.dumps({
        'public_authority_source': 'synthetic document',
        'highway_boundary_source': 'synthetic boundary',
        'access_restriction_source': 'synthetic restriction'}) + '\n')
    (folder / 'road.xodr').write_text('<OpenDRIVE>synthetic map fixture</OpenDRIVE>\n')
    (folder / 'native-road-readback.json').write_text(json.dumps({
        'source_kind': 'original_native_map_readback',
        'designation_source_sha256': module.digest(folder / 'designation-source.json'),
        'lanes': [{'road_id': 1, 'lane_id': lane}
                  for lane in (1, 2, -1) for _ in range(3)]}) + '\n')
    (folder / 'config.json').write_text(json.dumps({
        'case_id': case, 'law_id': 'NRS-484B-587-2a',
        'cell_id': 'C179776', 'actor': 'motor_vehicle_driver',
        'duration_s': 30, 'requested_speed_mps': 4}) + '\n')
    raw, controls, trace, frames = [], [], [], []
    for i in range(600):
        native = 1000 + i
        t = i / 20
        y = 5 if shoulder and i >= 200 else 2.5
        raw.append({'video_frame': i, 'native_frame': native, 'time_s': t,
                    'case_id': case, 'actors': [{'role': 'ego', 'actor_id': 5,
                    'blueprint_id': 'vehicle.synthetic', 'x_m': 132 - i * .2,
                    'y_m': y, 'yaw_deg': 180, 'bbox_half_length_m': 2,
                    'bbox_half_width_m': .9, 'speed_mps': 4}]})
        controls.append({'video_frame': i, 'native_frame': native, 'time_s': t,
                         'target_xy_m': [132 - i * .2, y]})
        trace.append({'frame': native, 'time_s': t,
                      'position_m': [132 - i * .2, y],
                      'position': {'x': 132 - i * .2, 'y': y, 'z': 0}})
        frames.append({'video_frame': i, 'native_frame': native, 'time_s': t,
                       'camera_native_frames': {name: native for name in module.CAMERAS}})
    for name, rows in (('native-raw-actors.jsonl', raw),
                       ('control-intent.jsonl', controls),
                       ('trace.jsonl', trace), ('video_frames.jsonl', frames)):
        write_lines(folder / name, rows)
    for name in module.CAMERAS:
        (folder / (name + '.mkv')).write_text('synthetic placeholder; not decoded\n')


def reject(folder, mutation, expected):
    mutation(folder)
    try:
        module.analyze(folder)
    except (ValueError, FileNotFoundError) as error:
        assert expected in str(error), str(error)
        return expected if isinstance(error, FileNotFoundError) else str(error)
    raise AssertionError('Corrupt saved source accepted')


with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
    base = Path(temporary)
    positives = {}
    for suffix, shoulder in (('probe_a', False), ('probe_b', True)):
        folder = base / suffix
        folder.mkdir()
        make(folder, suffix, shoulder)
        positives[suffix] = module.analyze(folder)
    assert positives['probe_a']['outside_marked_lane_frames'] == 0
    assert positives['probe_b']['outside_marked_lane_frames'] == 400
    assert positives['probe_b']['fully_paved_shoulder_frames'] == 400
    assert all(x['legal_verdict'] is None and not x['physical_original_verified'] for x in positives.values())
    finalized = module.finalize(base / 'probe_a', base / 'probe_a-analysis.json')
    assert finalized['outside_marked_lane_frames'] == 0
    assert finalized['measurements']['lane_footprint']['value']['outside_marked_lane_frames'] == 0
    assert module.measure_lane_footprint(positives['probe_b'])['value']['fully_paved_shoulder_frames'] == 400
    native_result = json.loads((base / 'probe_a' / 'result.json').read_text())
    assert native_result['physical_acceptance_claimed'] is False
    assert native_result['provenance_kind'] == 'synthetic_fixture'
    assert native_result['legal_verdict_claimed'] is False
    comparison_result = comparison.compare(base / 'probe_a', base / 'probe_b')
    assert comparison_result['passed'] is True
    negative = {}
    folder = base / 'missing_authority'; folder.mkdir(); make(folder, 'probe_a', False)
    negative['missing_authority'] = reject(folder, lambda p: (p / 'designation-source.json').write_text('{}\n'), 'designation source missing')
    folder = base / 'changed_binding'; folder.mkdir(); make(folder, 'probe_a', False)
    def changed_binding(path):
        authority = json.loads((path / 'designation-source.json').read_text())
        authority['public_authority_source'] = 'changed synthetic document'
        (path / 'designation-source.json').write_text(json.dumps(authority) + '\n')
    negative['changed_binding'] = reject(folder, changed_binding, 'designation source hash differs')
    folder = base / 'missing_video'; folder.mkdir(); make(folder, 'probe_a', False)
    negative['missing_video'] = reject(folder, lambda p: (p / 'overview.mkv').unlink(), 'overview.mkv')
    folder = base / 'frame_gap'; folder.mkdir(); make(folder, 'probe_a', False)
    def frame_gap(path):
        rows = module.load_lines(path / 'video_frames.jsonl')
        rows[300]['time_s'] = 99
        write_lines(path / 'video_frames.jsonl', rows)
    negative['frame_gap'] = reject(folder, frame_gap, 'camera frame/time map differs')
    folder = base / 'actor_gap'; folder.mkdir(); make(folder, 'probe_a', False)
    def actor_gap(path):
        rows = module.load_lines(path / 'native-raw-actors.jsonl')
        rows[300]['actors'][0]['actor_id'] = 99
        write_lines(path / 'native-raw-actors.jsonl', rows)
    negative['actor_gap'] = reject(folder, actor_gap, 'subject continuity missing')
    folder = base / 'comparison_wrong_map'; folder.mkdir(); make(folder, 'probe_b', True)
    (folder / 'road.xodr').write_text('<OpenDRIVE>changed</OpenDRIVE>\n')
    try:
        comparison.compare(base / 'probe_a', folder)
    except ValueError as error:
        assert 'Controlled fixed source differs' in str(error)
        negative['comparison_wrong_map'] = str(error)
    else:
        raise AssertionError('Changed comparison map accepted')
    folder = base / 'comparison_wrong_x'; folder.mkdir(); make(folder, 'probe_b', True)
    changed_rows = module.load_lines(folder / 'native-raw-actors.jsonl')
    changed_rows[300]['actors'][0]['x_m'] += 1
    write_lines(folder / 'native-raw-actors.jsonl', changed_rows)
    try:
        comparison.compare(base / 'probe_a', folder)
    except ValueError as error:
        assert 'longitudinal motion differs' in str(error)
        negative['comparison_wrong_x'] = str(error)
    else:
        raise AssertionError('Changed comparison longitudinal motion accepted')
    print(json.dumps({'passed': True, 'positive_cases': list(positives),
                      'negative': negative, 'saved_finalizer_executed': True,
                      'independent_comparison_passed': True,
                      'source_shaped_only': True,
                      'full_video_decode_claimed': False}, sort_keys=True))
