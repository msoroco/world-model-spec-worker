"""Create source-shaped CPU diagnostics for the four statutory branches."""
import hashlib
import json
import shutil
from pathlib import Path

from branch_scenarios import BRANCHES, rows

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def write_rows(path, rows_):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows_))


def move_vertices(vertices, dx, dy):
    return [[point[0] + dx, point[1] + dy, point[2]] for point in vertices]


def build():
    base = ROOT / 'selected-source-controlled_1'
    existing_manifest = json.loads((ROOT / 'selected-compatibility-manifest.json').read_text())
    model = existing_manifest['cases'][0]
    selected_manifest = {'format': 'worker-execution-manifest',
                         'assignment_id': ROOT.name, 'cases': [],
                         'runtime_manifest_sha256': existing_manifest['runtime_manifest_sha256']}
    proposals = json.loads((ROOT / 'native/selected-branch-constructions.json').read_text())
    by_case = {}
    for entry in proposals:
        by_case.setdefault(entry['case'], {})[entry['candidate']] = entry
    for case in BRANCHES:
        source = ROOT / ('selected-source-' + case)
        source.mkdir(exist_ok=True)
        for item in base.rglob('*'):
            if item.is_file():
                destination = source / item.relative_to(base)
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(item, destination)
        request = rows(case)
        write_rows(source / 'turn-history.jsonl', request)
        trace = [json.loads(line) for line in (source / 'trace.jsonl').read_text().splitlines()]
        evidence = [json.loads(line) for line in (source / 'capture/evidence.jsonl').read_text().splitlines()]
        if len(trace) != 600 or len(evidence) != 600:
            raise ValueError('Retained diagnostic frame inventory differs')
        for frame in range(600):
            ego = request[frame]['requested_ego_xy_m']
            before = request[max(0, frame - 1)]['requested_ego_xy_m']
            after = request[min(599, frame + 1)]['requested_ego_xy_m']
            interval = 0.05 if frame in (0, 599) else 0.10
            velocity = [(after[0] - before[0]) / interval,
                        (after[1] - before[1]) / interval, 0.0]
            speed = (velocity[0] ** 2 + velocity[1] ** 2) ** 0.5
            old = trace[frame]['position_m']
            dx, dy = ego[0] - old[0], ego[1] - old[1]
            trace[frame]['position_m'] = [ego[0], ego[1], 0.5]
            trace[frame]['position'] = {'x': ego[0], 'y': ego[1], 'z': 0.5}
            trace[frame]['velocity_mps'] = velocity
            trace[frame]['speed_mps'] = speed
            trace[frame]['speed_mph'] = speed * 2.2369362920544
            event = evidence[frame]
            event['ego']['position_m'] = [ego[0], ego[1], 0.5]
            event['ego']['body_vertices_m'] = move_vertices(event['ego']['body_vertices_m'], dx, dy)
            event['ego']['speed_mps'] = speed
            other = event['other_actors'][0]
            old_other = other['position_m']
            target_other = request[frame]['requested_other_xy_m']
            odx, ody = target_other[0] - old_other[0], target_other[1] - old_other[1]
            other['position_m'] = [target_other[0], target_other[1], 0.5]
            other['body_vertices_m'] = move_vertices(other['body_vertices_m'], odx, ody)
        write_rows(source / 'trace.jsonl', trace)
        write_rows(source / 'capture/evidence.jsonl', evidence)
        context = json.loads((source / 'arrow-context.json').read_text())
        context.update(case_id=ROOT.name + '__' + case,
                       branch=BRANCHES[case]['branch'],
                       requested_concurrent_straight_indication=BRANCHES[case]['concurrent_straight'])
        dump(source / 'arrow-context.json', context)
        capture = json.loads((source / 'capture/manifest.json').read_text())
        capture['sources']['trace.jsonl'] = sha(source / 'trace.jsonl')
        dump(source / 'capture/manifest.json', capture)
        files = [{'path': str(item.relative_to(source)),
                  'source': str(item.relative_to(REPO)), 'sha256': sha(item)}
                 for item in sorted(source.rglob('*')) if item.is_file()]
        old = json.loads((ROOT / 'selected-controlled_1-fixture-recipe.json').read_text())
        recipe = ROOT / ('selected-' + case + '-fixture-recipe.json')
        dump(recipe, {'format': 'worker-fixture-recipe', 'sources': files,
                      'generator': old['generator']})
        main = by_case[case]['primary']
        fallback = by_case[case]['fallback1']
        entry = dict(model)
        entry.update(case_id=ROOT.name + '__' + case,
                     construction=main['construction'],
                     construction_sha256=main['sha256'],
                     fixture_recipe=str(recipe.relative_to(REPO)),
                     measurement_contract='measurement-contract-' + case + '.json',
                     candidate_risk={'status': 'physical',
                                     'reason': 'Ego may stall before source-defined intersection entry'},
                     candidates=[{'id': 'fallback1',
                                  'construction': fallback['construction'],
                                  'construction_sha256': fallback['sha256'],
                                  'changed_knobs': ['ego throttle 0.22 to 0.28; intervention fixed'],
                                  'trigger': {'source': 'original Native turn-history.jsonl',
                                              'metric': 'ego reaches source-defined intersection',
                                              'failure_condition': 'primary ego never enters within 600 frames'}}])
        selected_manifest['cases'].append(entry)
        contract = json.loads((ROOT / 'measurement-contract-controlled_1.json').read_text())
        contract['case_id'] = ROOT.name + '__' + case
        contract['requirements'][0]['disposition_index'] = (1 if case.startswith('pedestrian_') else 2)
        contract['requirements'][0]['output_key'] = 'statutory_branch_measurement'
        dump(ROOT / ('measurement-contract-' + case + '.json'), contract)
    dump(ROOT / 'selected-branch-compatibility-manifest.json', selected_manifest)


if __name__ == '__main__':
    build()
