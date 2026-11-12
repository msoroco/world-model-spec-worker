"""Construct an opposite-direction straight-through diagnostic case.

The road and evidence here are synthetic CPU inputs, not a reviewed Native site.
"""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__source_verified_opposite_straight'
BASE = ROOT.name + '__source_verified_other_right_near_time'
OUT = ROOT / 'cases/source_verified_opposite_straight'


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(value):
    return hashlib.sha256(value.encode()).hexdigest()


def lines(rows):
    return ''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows)


def box(x, y):
    return [[x-.3, y-.3], [x+.3, y-.3], [x+.3, y+.3], [x-.3, y+.3]]


def other_x(index):
    return 8 if index < 20 else max(-8, 8-.8*(index-20))


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    construction = copy.deepcopy(json.loads((ROOT / 'construction.json').read_text()))
    construction['case_id'] = CASE
    construction['status'] = 'synthetic_diagnostic_only'
    files = {item['path']: item for item in construction['files']}
    config = json.loads(files['config.json']['content'])
    config['selected_case_id'] = CASE
    config['supported_case_ids'] = [entry['case_id'] for entry in
        json.loads((ROOT / 'execution-manifest.json').read_text())['cases']] + [CASE]
    config['other_intent'] = 'straight'
    site = config['site']
    site['other_approach'] = [10, 3.5, 0, 180]
    site['other_entry'] = [4, 3.5, 0, 180]
    site['routes']['other'] = [[10, 3.5], [4, 3.5], [0, 3.5], [-10, 3.5]]
    packet = json.loads(files['site-review.json']['content'])
    packet['site'] = site
    packet_text = dump(packet)
    files['site-review.json']['content'] = packet_text
    config['site_review']['sha256'] = sha(packet_text)
    files['config.json']['content'] = dump(config)
    runner = files['runner.py']['content'].replace(BASE, CASE)
    check = '    verify_site_packet(config, base_dir)\n    return config'
    if runner.count(check) != 1:
        raise ValueError('Runner config validation changed')
    runner = runner.replace(check,
        '    if config.get("other_intent") != "straight":\n'
        '        raise ValueError("Opposite straight intention required")\n'
        '    verify_site_packet(config, base_dir)\n    return config')
    write_after = '                (output / "road_geometry.json").write_text(json.dumps(geometry, indent=2) + "\\n")'
    if runner.count(write_after) != 1:
        raise ValueError('Runner road geometry capture changed')
    runner = runner.replace(write_after, write_after + '\n'
        '                (output / "turn_intent.json").write_text(json.dumps({"actor_id": 102, '
        '"intended_maneuver": config["other_intent"], "source": "authored diagnostic config"}) + "\\n")')
    files['runner.py']['content'] = runner
    pair = files['native_pair.py']['content']
    old = 'if lateral <= 0 or reciprocal >= 0:\n        raise ValueError("Other Native approach is not on ego right")'
    new = ('heading_gap = abs((approaches["ego"]["heading_deg"] - approaches["other"]["heading_deg"] + 180) % 360 - 180)\n'
           '    if heading_gap < 165 or approaches["other"]["start_xy_m"][0] <= approaches["ego"]["start_xy_m"][0] + 10:\n'
           '        raise ValueError("Opposite Native approaches and headings required")')
    if pair.count(old) != 1:
        raise ValueError('Native side condition changed')
    files['native_pair.py']['content'] = pair.replace(old, new)
    entry = files['entry_measurements.py']['content']
    old = '    if (ego_right > 0) == (other_right > 0):\n        raise ValueError("Approach sides are not reciprocal")'
    new = ('    heading_difference = ((geometry["other_approach_heading_deg"] -\n'
           '                           geometry["ego_approach_heading_deg"] + 180) % 360 - 180)\n'
           '    opposite = abs(abs(heading_difference) - 180) <= 15\n'
           '    if not opposite:\n        raise ValueError("Opposite sourced approach headings required")')
    if entry.count(old) != 1:
        raise ValueError('Entry approach geometry check changed')
    entry = entry.replace(old, new)
    entry = entry.replace('"geometric_yield_candidate": "ego" if ego_right > 0 else "other",',
                          '"geometric_yield_candidate": "not_applicable_opposite_straight",\n'
                          '        "opposite_directions": opposite,')
    files['entry_measurements.py']['content'] = entry
    finalizer = files['finalizer.py']['content']
    finalizer = finalizer.replace('"controller_history.jsonl",\n                "video_frames.jsonl"',
        '"controller_history.jsonl", "turn_intent.json",\n                "video_frames.jsonl"')
    marker = '\ndef finalize(attempt: Path, output: Path):'
    if finalizer.count(marker) != 1:
        raise ValueError('Saved finalizer entrypoint changed')
    method = '''\ndef measure_opposite_approach(attempt, geometry, report):
    intent = json.loads((attempt / "turn_intent.json").read_text())
    if intent.get("actor_id") != 102 or intent.get("intended_maneuver") != "straight":
        raise ValueError("Missing authored opposite straight intention")
    evidence = [json.loads(line) for line in (attempt / "capture/evidence.jsonl").read_text().splitlines() if line.strip()]
    headings = [next(p["heading_deg"] for p in row["original_observations"]["participants"]
                     if p["actor_id"] == 102) for row in evidence]
    if len(headings) < 2 or any(abs((heading - 180 + 180) % 360 - 180) > 15 for heading in headings):
        raise ValueError("Other original heading did not remain straight")
    if abs(abs(report["approach_heading_difference_deg"]) - 180) > 15:
        raise ValueError("Original approaches were not opposite")
    return {"method": "measure_opposite_approach",
            "value": {"approach_heading_difference_deg": report["approach_heading_difference_deg"],
                      "intended_maneuver": "straight", "observed_heading_range_deg":
                      [min(headings), max(headings)], "left_turn_exception_judgment": "unresolved"},
            "sources": {name: _sha(attempt / name) for name in
                        ("road_geometry.json", "capture/evidence.jsonl", "turn_intent.json")}}
'''
    finalizer = finalizer.replace(marker, method + marker)
    finalizer = finalizer.replace('"yield_control_attempt": control,',
        '"yield_control_attempt": control,\n'
        '        "opposite_approach": measure_opposite_approach(attempt, geometry, report),')
    files['finalizer.py']['content'] = finalizer
    files['tests/test_bundle.py']['content'] = files['tests/test_bundle.py']['content'].replace(
        "self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])",
        "self.assertEqual(validate_config(config)['selected_case_id'],config['selected_case_id'])\n"
        "  self.assertEqual(config['other_intent'],'straight')")
    ctext = dump(construction)
    (OUT / 'construction.json').write_text(ctext)
    diagnostic = copy.deepcopy(json.loads((ROOT / 'diagnostic.json').read_text()))
    sources = diagnostic['files']
    history = [json.loads(row) for row in sources['crossing_history.jsonl'].splitlines()]
    evidence = [json.loads(row) for row in sources['capture/evidence.jsonl'].splitlines()]
    for index, (row, observation) in enumerate(zip(history, evidence)):
        x = other_x(index)
        row['other']['position_xy_m'] = [x, 3.5]
        row['other']['body_vertices_xy_m'] = box(x, 3.5)
        participant = next(p for p in observation['original_observations']['participants'] if p['actor_id'] == 102)
        participant['position_m'] = [x, 3.5, 0]
        participant['body_vertices_m'] = [[px, py, z] for px, py in box(x, 3.5) for z in (0, 1.5)]
        participant['heading_deg'] = 180
        participant['velocity_mps'] = [-participant['speed_mps'], 0, 0]
        for graph in diagnostic['graphs'][2*index:2*index+2]:
            graph['attributes']['observed_evidence'] = copy.deepcopy(observation['original_observations'])
    sources['crossing_history.jsonl'] = lines(history)
    sources['capture/evidence.jsonl'] = lines(evidence)
    sources['turn_intent.json'] = dump({'actor_id': 102, 'intended_maneuver': 'straight',
                                       'source': 'authored diagnostic config'})
    geometry = json.loads(sources['road_geometry.json'])
    geometry['other_approach_heading_deg'] = 180
    geometry['other_approach_origin_xy_m'] = [8, 3.5]
    sources['road_geometry.json'] = dump(geometry)
    xodr = sources['road.xodr']
    old = 'synthetic other highway" length="30" id="2" junction="7"><link/><planView><geometry s="0" x="0" y="-15" hdg="1.5707963267948966"'
    new = 'synthetic other highway" length="30" id="2" junction="7"><link/><planView><geometry s="0" x="15" y="3.5" hdg="3.141592653589793"'
    if xodr.count(old) != 1:
        raise ValueError('Other synthetic OpenDRIVE road changed')
    sources['road.xodr'] = xodr.replace(old, new)
    capture = json.loads(sources['capture/manifest.json'])
    capture['case_id'] = CASE
    capture['sources']['road.xodr'] = sha(sources['road.xodr'])
    sources['capture/manifest.json'] = dump(capture)
    path = OUT / 'diagnostic.json'
    path.write_text(dump(diagnostic))
    origin = OUT / 'fixture-origin.json'
    origin.write_text(dump({'format': 'worker-synthetic-diagnostic-origin',
                            'case_id': CASE, 'physical_evidence': False,
                            'purpose': 'CPU compatibility only'}))
    def ref(file):
        return {'source': str(file.relative_to(REPO)),
                'sha256': hashlib.sha256(file.read_bytes()).hexdigest()}
    (OUT / 'diagnostic-recipe.json').write_text(dump({
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'fixture-origin.json', **ref(origin)}], 'generator': ref(path)}))
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for index in (0, 2):
        if CASE not in plan['requirement_dispositions'][index]['case_ids']:
            plan['requirement_dispositions'][index]['case_ids'].append(CASE)
    requirement = 'Original opposite approach headings, authored straight intention and observed straight heading history distinguish the left-turn exclusion without deciding legal applicability'
    source = 'NRS 484B.250(2); inputs/' + ROOT.name + '/assignment.json'
    found = next((i for i, row in enumerate(plan['requirement_dispositions'])
                  if row['requirement'] == requirement), None)
    if found is None:
        found = len(plan['requirement_dispositions'])
        plan['requirement_dispositions'].append({'requirement': requirement, 'source': source,
            'status': 'selected_required', 'case_ids': [CASE],
            'output_key': 'opposite_approach',
            'evidence_or_gap': 'Synthetic CPU sources only; original Native approach and intention unverified'})
    elif CASE not in plan['requirement_dispositions'][found]['case_ids']:
        plan['requirement_dispositions'][found]['case_ids'].append(CASE)
    plan_path.write_text(dump(plan))
    contract = copy.deepcopy(json.loads((ROOT / 'measurement-contract.json').read_text()))
    contract['requirements'] = [row for row in contract['requirements'] if row['disposition_index'] in (0, 2)]
    contract['requirements'].append({'disposition_index': found, 'requirement': requirement,
        'source': source, 'output_key': 'opposite_approach', 'method': 'measure_opposite_approach',
        'value_type': 'object', 'kind': 'measured',
        'inputs': ['road_geometry.json', 'capture/evidence.jsonl', 'turn_intent.json']})
    contract['negative'] = {'remove': ['turn_intent.json'],
                            'error_contains': 'Missing required source: turn_intent.json'}
    (OUT / 'measurement-contract.json').write_text(dump(contract))
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if CASE not in {entry['case_id'] for entry in manifest['cases']}:
        item = copy.deepcopy(manifest['cases'][0])
        item.update({'case_id': CASE,
                     'construction': str((OUT / 'construction.json').relative_to(ROOT)),
                     'construction_sha256': sha(ctext),
                     'fixture_recipe': str((OUT / 'diagnostic-recipe.json').relative_to(REPO)),
                     'measurement_contract': str((OUT / 'measurement-contract.json').relative_to(ROOT)),
                     'candidate_risk': {'status': 'physical',
                                        'reason': 'Opposite Native lane or straight trajectory may miss one crossing or camera'},
                     'candidates': []})
        for key in ('offline', 'compatibility', 'negative'):
            item.pop(key, None)
        manifest['cases'].append(item)
        manifest_path.write_text(dump(manifest))
    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    if CASE not in {row['case_id'] for row in proposals['cases']}:
        row = copy.deepcopy(proposals['cases'][0])
        row['case_id'] = CASE
        row['rationale'] = 'Opposite straight approach and intention; synthetic CPU diagnostic only'
        proposals['cases'].append(row)
        proposals_path.write_text(dump(proposals))
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(ctext),
                      'diagnostic_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == '__main__':
    build()
