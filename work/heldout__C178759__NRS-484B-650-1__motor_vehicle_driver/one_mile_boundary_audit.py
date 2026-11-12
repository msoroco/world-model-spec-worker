"""Independent requested-station comparison; no Native or legal finding."""
import argparse
import ast
from hashlib import sha256
import json
from pathlib import Path

PREFIX = 'heldout__C178759__NRS-484B-650-1__motor_vehicle_driver__'
NAMES = ('repeated_right_pass', 'at_mile', 'beyond_mile')
MILE_M = 1609.344
FIXED_SOURCE_FILES = ('video_frames.jsonl', 'trace.jsonl', 'driving_trace.jsonl',
                      'following_sources.jsonl', 'right_pass_sources.jsonl', 'road.xodr')


def read(path):
    return json.loads(Path(path).read_text())


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def phase_rows(construction):
    code = next(f['content'] for f in construction['files']
                if f['path'] == 'two_pass_construction.py')
    tree = ast.parse(code)
    assignment = next(node for node in tree.body if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == 'PHASES'
                              for t in node.targets))
    rows = []
    for call in assignment.value.elts:
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != 'Phase':
            raise ValueError('Controller phase inventory is not declarative')
        rows.append(tuple(ast.literal_eval(arg) for arg in call.args))
    names = [row[0] for row in rows]
    if names != ['approach', 'first_right_pass_request', 'first_reentry',
                 'lead_reclaim_request', 'second_reentry',
                 'second_right_pass_request', 'exit']:
        raise ValueError('Two-pass controller phase order changed')
    if any(a[2] != b[1] for a, b in zip(rows, rows[1:])):
        raise ValueError('Controller station schedule has a gap')
    return rows


def source_rows(text):
    return [json.loads(row) for row in text.splitlines() if row.strip()]


def audit(folder, *, diagnostics=None):
    folder = Path(folder)
    manifest = read(folder / 'execution-manifest.json')
    entries = {entry['case_id']: entry for entry in manifest['cases']}
    if not all(PREFIX + name in entries for name in NAMES):
        raise ValueError('Below/at/above exact cases missing')
    diagnostics = diagnostics or {}
    constructions, sources, schedules, receipts = {}, {}, {}, {}
    for name in NAMES:
        entry = entries[PREFIX + name]
        path = folder / entry['construction']
        if digest(path) != entry['construction_sha256']:
            raise ValueError('Threshold construction hash stale: ' + name)
        construction = read(path)
        if construction['case_id'] != PREFIX + name:
            raise ValueError('Threshold case identity changed: ' + name)
        constructions[name] = construction
        schedules[name] = phase_rows(construction)
        recipe = read(folder.parents[1] / entry['fixture_recipe'])
        diagnostic_path = folder.parents[1] / recipe['sources'][0]['source']
        if digest(diagnostic_path) != recipe['sources'][0]['sha256']:
            raise ValueError('Threshold source recipe changed: ' + name)
        sources[name] = diagnostics.get(name) or read(diagnostic_path)
        receipt = read(folder / entry['compatibility']['receipt'])
        if (digest(folder / entry['compatibility']['receipt']) != entry['compatibility']['sha256']
                or receipt['case_id'] != PREFIX + name
                or receipt['construction_sha256'] != entry['construction_sha256']
                or receipt['scope'] != 'diagnostic software compatibility only'):
            raise ValueError('Threshold compatibility source binding differs: ' + name)
        receipts[name] = receipt
    fixed_config = ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames', 'duration_s',
                    'required_atoms', 'source_packets', 'cameras', 'engineering')
    configs = {name: json.loads(next(f['content'] for f in constructions[name]['files']
                                     if f['path'] == 'config.json')) for name in NAMES}
    baseline = configs[NAMES[0]]
    for name in NAMES[1:]:
        if any(configs[name][key] != baseline[key] for key in fixed_config):
            raise ValueError('Threshold fixed capture or engineering context changed: ' + name)
        if constructions[name]['recording_description'] != constructions[NAMES[0]]['recording_description']:
            raise ValueError('Threshold recording observations changed: ' + name)
        if schedules[name][:4] != schedules[NAMES[0]][:4]:
            raise ValueError('First pass or lead reset changed: ' + name)
        for source_name in FIXED_SOURCE_FILES:
            if sources[name]['files'][source_name] != sources[NAMES[0]]['files'][source_name]:
                raise ValueError('Fixed original source differs: ' + source_name)
    source = sources[NAMES[0]]['files']
    frame_map = source_rows(source['video_frames.jsonl'])
    drive = source_rows(source['driving_trace.jsonl'])
    actors = source_rows(source['following_sources.jsonl'])
    passes = source_rows(source['right_pass_sources.jsonl'])
    if not frame_map or not len(frame_map) == len(drive) == len(actors) == len(passes):
        raise ValueError('Threshold source frame coverage differs')
    actor_ids = set()
    for index, (frame, motion, bodies, road) in enumerate(zip(frame_map, drive, actors, passes)):
        key = (frame['carla_frame'], frame['time_s'])
        if frame['video_frame'] != index or any((row['frame'], row['time_s']) != key
                                                for row in (motion, bodies, road)):
            raise ValueError('Threshold source frame/time join differs')
        ids = (bodies['ego']['actor_id'], bodies['lead']['actor_id'])
        if (road['ego_actor_id'], road['fixed_overtaken_actor_id']) != ids:
            raise ValueError('Threshold fixed overtaken actor differs')
        actor_ids.add(ids)
    if len(actor_ids) != 1:
        raise ValueError('Threshold source participant changes')
    spans, finish_s, fixture_spans = {}, {}, {}
    for name in NAMES:
        rows = schedules[name]
        first, second = rows[1], rows[5]
        if first[1] != 260 or first[3] != 'right_of_paved_edge' or second[3] != 'right_of_paved_edge':
            raise ValueError('Right-pass request station or target differs')
        spans[name] = second[2] - first[1]
        finish_s[name] = sum((row[2] - row[1]) / row[4] for row in rows[:6])
        if finish_s[name] >= 100:
            raise ValueError('Second pass nominally finishes after capture')
        measured = receipts[name]['measurement_examples']['two_right_pass_observation']['value']
        if measured['source_status'] != 'candidate' or len(measured['episodes']) != 2:
            raise ValueError('Diagnostic two-pass source candidate differs')
        fixture_spans[name] = measured['event_envelope']['conduct_envelope_m']
    if not spans[NAMES[0]] < MILE_M or abs(spans[NAMES[1]] - MILE_M) > 1e-6 or not spans[NAMES[2]] > MILE_M:
        raise ValueError('Requested below/at/above one-mile stations absent')
    if not all(value < MILE_M for value in fixture_spans.values()):
        raise ValueError('Diagnostic scope unexpectedly changed')
    return {'format': 'worker-one-mile-boundary-audit', 'comparison_id': 'C178759_one_mile_boundary',
            'case_ids': [PREFIX + name for name in NAMES],
            'construction_sha256': {name: entries[PREFIX + name]['construction_sha256'] for name in NAMES},
            'fixed_original_frames': len(frame_map), 'fixed_actor_ids': sorted(actor_ids),
            'requested_station_span_m': spans, 'nominal_second_pass_finish_s': finish_s,
            'diagnostic_measured_envelope_m': fixture_spans,
            'auditor_sha256': digest(__file__),
            'scope': 'requested controller stations and identical short original-shaped diagnostic sources only; actual one-mile Native path remains unmeasured',
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior threshold comparison audit')
    output.write_text(json.dumps(audit(args.folder), indent=2) + '\n')


if __name__ == '__main__':
    main()
