"""Build the sourced wide-roadway diagnostic, retaining crossing motion."""

import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OLD = ROOT.name + '__source_verified_other_right_near_time'
CASE = ROOT.name + '__source_verified_wide_separate_crossing'
OUT = ROOT / 'cases/source_verified_wide_separate_crossing'


def dump(value):
    return json.dumps(value, indent=2, allow_nan=False) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def change(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Expected one occurrence of {old!r}; found {text.count(old)}')
    return text.replace(old, new)


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    construction = copy.deepcopy(json.loads((ROOT / 'construction.json').read_text()))
    construction['case_id'] = CASE
    files = {row['path']: row for row in construction['files']}
    config = json.loads(files['config.json']['content'])
    config['selected_case_id'] = CASE
    config['supported_case_ids'] = list(config['supported_case_ids']) + [CASE]
    config['site']['same_statutory_crossing_reviewed'] = False
    median_path = 'site-sources/median_spacing_source.json'
    median = json.loads(files[median_path]['content'])
    median['source_description'] = 'synthetic CPU selected roadway and second roadway separated by 12 m edge gap'
    median['roadway_polygons_xy_m'][1] = [[-5, 17], [5, 17], [5, 27], [-5, 27]]
    files[median_path]['content'] = dump(median)
    packet = json.loads(files['site-review.json']['content'])
    packet['site'] = config['site']
    packet['source_documents']['median_spacing_source']['sha256'] = hashlib.sha256(files[median_path]['content'].encode()).hexdigest()
    files['site-review.json']['content'] = dump(packet)
    config['site_review']['sha256'] = hashlib.sha256(files['site-review.json']['content'].encode()).hexdigest()
    files['config.json']['content'] = dump(config)
    runner = change(files['runner.py']['content'], OLD, CASE)
    runner = change(runner,
                    'if site.get("same_statutory_crossing_reviewed") is not True:\n'
                    '        raise ValueError("Statutory crossing identity review required")',
                    'if site.get("same_statutory_crossing_reviewed") is not False:\n'
                    '        raise ValueError("Separate-crossing candidate must preserve unresolved statutory identity")')
    runner = change(runner,
        '                (output / "road_geometry.json").write_text(json.dumps(geometry, indent=2) + "\\n")',
        '                (output / "road_geometry.json").write_text(json.dumps(geometry, indent=2) + "\\n")\n'
        '                (output / "median_geometry_source.json").write_bytes('
        'Path(reviewed["source_documents"]["median_spacing_source"]["path"]).read_bytes())')
    files['runner.py']['content'] = runner
    finalizer = files['finalizer.py']['content']
    finalizer = change(finalizer, 'from entry_measurements import analyze',
                       'from entry_measurements import analyze\nfrom median_spacing import check_roadway_pair')
    marker = '\ndef finalize(attempt: Path, output: Path):'
    method = '''\ndef measure_wide_crossing(attempt, geometry):
    source = "median_geometry_source.json"
    document = json.loads((attempt / source).read_text())
    value = check_roadway_pair(document, geometry["intersection_polygon_xy_m"], 0)
    if value["boundary_relation"] != "above" or not value["separate_roadway_crossings_geometry_candidate"]:
        raise ValueError("Sourced wide separate roadway geometry required")
    return {"method": "measure_wide_crossing", "value": value,
            "sources": {source: _sha(attempt / source),
                        "road_geometry.json": _sha(attempt / "road_geometry.json")}}
'''
    finalizer = change(finalizer, marker, method + marker)
    finalizer = change(finalizer, '"controller_history.jsonl",\n                "video_frames.jsonl"',
                       '"controller_history.jsonl", "median_geometry_source.json",\n                "video_frames.jsonl"')
    finalizer = change(finalizer, '"yield_control_attempt": control,',
                       '"yield_control_attempt": control,\n        "median_crossing_geometry": measure_wide_crossing(attempt, geometry),')
    files['finalizer.py']['content'] = finalizer
    construction_path = OUT / 'construction.json'
    construction_path.write_text(dump(construction))

    diagnostic = copy.deepcopy(json.loads((ROOT / 'diagnostic.json').read_text()))
    diagnostic['files']['median_geometry_source.json'] = dump(median)
    capture = json.loads(diagnostic['files']['capture/manifest.json'])
    capture['case_id'] = CASE
    diagnostic['files']['capture/manifest.json'] = dump(capture)
    diagnostic_path = OUT / 'diagnostic.json'
    diagnostic_path.write_text(dump(diagnostic))
    origin = OUT / 'fixture-origin.json'
    origin.write_text(dump({'format': 'worker-synthetic-diagnostic-origin',
                            'case_id': CASE, 'physical_evidence': False,
                            'purpose': 'CPU compatibility only'}))
    def ref(path):
        return {'source': str(path.relative_to(REPO)), 'sha256': sha(path)}
    (OUT / 'diagnostic-recipe.json').write_text(dump({
        'format': 'worker-fixture-recipe',
        'sources': [{'path': 'fixture-origin.json', **ref(origin)}],
        'generator': ref(diagnostic_path)}))
    requirement = ('Sourced roadway footprints measure a median edge gap above 9.144 m '
                   'and isolate the selected crossing polygon without deciding statutory crossing identity')
    source = 'NRS 484B.250(2); inputs/' + ROOT.name + '/assignment.json'
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    for index in (0, 2):
        if CASE not in plan['requirement_dispositions'][index]['case_ids']:
            plan['requirement_dispositions'][index]['case_ids'].append(CASE)
    found = next((i for i, row in enumerate(plan['requirement_dispositions'])
                  if row['requirement'] == requirement), None)
    if found is None:
        found = len(plan['requirement_dispositions'])
        plan['requirement_dispositions'].append({
            'requirement': requirement, 'source': source, 'status': 'selected_required',
            'case_ids': [CASE], 'output_key': 'median_crossing_geometry',
            'evidence_or_gap': 'Synthetic CPU roadway polygons; physical and statutory identity unresolved'})
    plan_path.write_text(dump(plan))
    contract = copy.deepcopy(json.loads((ROOT / 'measurement-contract.json').read_text()))
    contract['requirements'] = [row for row in contract['requirements'] if row['disposition_index'] in (0, 2)]
    contract['requirements'].append({
        'disposition_index': found, 'requirement': requirement, 'source': source,
        'output_key': 'median_crossing_geometry', 'method': 'measure_wide_crossing',
        'value_type': 'object', 'kind': 'measured',
        'inputs': ['median_geometry_source.json', 'road_geometry.json']})
    contract['negative'] = {'remove': ['median_geometry_source.json'],
                            'error_contains': 'Missing required source: median_geometry_source.json'}
    (OUT / 'measurement-contract.json').write_text(dump(contract))
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    row = next((row for row in manifest['cases'] if row['case_id'] == CASE), None)
    if row is None:
        row = copy.deepcopy(manifest['cases'][0])
        manifest['cases'].append(row)
    row.update({'case_id': CASE, 'construction': str(construction_path.relative_to(ROOT)),
                'construction_sha256': sha(construction_path),
                'fixture_recipe': str((OUT / 'diagnostic-recipe.json').relative_to(REPO)),
                'measurement_contract': str((OUT / 'measurement-contract.json').relative_to(ROOT)),
                'candidate_risk': {'status': 'physical',
                                   'reason': 'Wide second roadway may not match Native site or four-camera coverage'},
                'candidates': []})
    for key in ('offline', 'compatibility', 'negative'):
        row.pop(key, None)
    manifest_path.write_text(dump(manifest))
    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    if CASE not in {row['case_id'] for row in proposals['cases']}:
        row = copy.deepcopy(proposals['cases'][0])
        row['case_id'] = CASE
        row['rationale'] = 'Sourced synthetic 12 m roadway-edge gap and selected crossing; statutory identity unresolved'
        proposals['cases'].append(row)
        proposals_path.write_text(dump(proposals))
    print(json.dumps({'case_id': CASE, 'construction_sha256': sha(construction_path),
                      'diagnostic_sha256': sha(diagnostic_path)}))


if __name__ == '__main__':
    build()
