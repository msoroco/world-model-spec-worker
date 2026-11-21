"""Construct a separate lawful reverse control without changing the corner pair."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE_ID = HERE.name + '__control'


def replace(source, old, new):
    if old not in source:
        raise ValueError('Expected construction fragment absent: ' + old)
    return source.replace(old, new)


def build(candidate):
    source = HERE / 'cases/condition_a' / candidate / 'construction.json'
    bundle = copy.deepcopy(json.loads(source.read_text()))
    bundle['case_id'] = CASE_ID
    for item in bundle['files']:
        path, content = item['path'], item['content']
        if path == 'geometry.py':
            content = replace(content, "('condition_a','condition_b')", "('condition_a','condition_b','condition_c')")
            content = replace(content, "if suffix=='condition_a':return (12-distance,-1.75,0.)",
                              "if suffix=='condition_a':return (12-distance,-1.75,0.)\n    if suffix=='condition_c':return (25-distance,-1.75,0.)")
            content = replace(content, "if junction<=0:raise ValueError('Intersection context absent')",
                              "if suffix=='condition_c' and junction>0:raise ValueError('Control enters intersection')\n        if suffix!='condition_c' and junction<=0:raise ValueError('Intersection context absent')")
            content = replace(content, "(suffix=='condition_a' and turning_frames)",
                              "(suffix in ('condition_a','condition_c') and turning_frames)")
            content = replace(content, "if overlap(body(*START),INTERSECTION) or overlap(body(*START),CROSSWALK):",
                              "if overlap(body(*START),INTERSECTION) or overlap(body(*START),CROSSWALK) or overlap(body(25.,-1.75,0.),INTERSECTION):")
        elif path == 'engineering.py':
            content = replace(content, "CASES=('condition_a','condition_b')",
                              "CASES=('condition_a','condition_b','condition_c')")
        elif path == 'controller.py':
            content = replace(content, "('condition_a','condition_b')", "('condition_a','condition_b','condition_c')")
        elif path == 'measure.py':
            content = replace(content, 'max_crosswalk_overlap=0',
                              'max_crosswalk_overlap=0;max_intersection_overlap=0')
            content = replace(content, 'if reverse<-.05:\n            backing+=1',
                              'if reverse<-.05:\n            max_intersection_overlap=max(max_intersection_overlap,overlap(body,INTERSECTION))\n            backing+=1')
            content = replace(content,
                "'relation':'backing_around_street_corner' if turning>=20 and max_heading>=30 else 'backing_straight_through_intersection'",
                "'relation':'backing_clear_of_intersection' if max_intersection_overlap==0 else ('backing_around_street_corner' if turning>=20 and max_heading>=30 else 'backing_straight_through_intersection')")
            content = replace(content, "'max_backing_crosswalk_overlap_m2':round(max_crosswalk_overlap,5),",
                              "'max_backing_crosswalk_overlap_m2':round(max_crosswalk_overlap,5),\n            'max_backing_intersection_overlap_m2':round(max_intersection_overlap,5),")
        elif path == 'finalize.py':
            content = replace(content, "'condition_b':'backing_around_street_corner'}[config['case_suffix']]",
                              "'condition_b':'backing_around_street_corner','condition_c':'backing_clear_of_intersection'}[config['case_suffix']]")
            content = replace(content, "'condition_b':[1.75,4.5]}[config['case_suffix']]",
                              "'condition_b':[1.75,4.5],'condition_c':[11.182522957531896,-1.75]}[config['case_suffix']]")
        elif path == 'runner.py':
            content = replace(content, '("condition_a","condition_b")',
                              '("condition_a","condition_b","condition_c")')
            content = replace(content, "{'condition_a':'false','condition_b':'true'}",
                              "{'condition_a':'false','condition_b':'true','condition_c':'control'}")
            content = replace(content, 'carla.Location(x=12,y=-1.75,z=.5)',
                              "carla.Location(x=25 if config['case_suffix']=='condition_c' else 12,y=-1.75,z=.5)")
            content = replace(content, 'if not all(-3.5<y<0 and 7<x<15 for x,y in initial):',
                              "if not all(-3.5<y<0 and (20<x<28 if config['case_suffix']=='condition_c' else 7<x<15) for x,y in initial):")
        elif path == 'config.json':
            config = json.loads(content)
            config['case_id'] = CASE_ID
            config['selected_case_id'] = CASE_ID
            config['case_suffix'] = 'condition_c'
            config['supported_case_ids'] = [HERE.name + '__false', HERE.name + '__true', CASE_ID]
            if isinstance(config.get('case'), dict):
                config['case']['case_id'] = CASE_ID
            content = json.dumps(config, indent=2) + '\n'
        item['content'] = content
    destination = HERE / 'cases/condition_c' / candidate / 'construction.json'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(bundle, indent=2) + '\n')
    return destination


if __name__ == '__main__':
    rows = []
    for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        path = build(candidate)
        rows.append({'candidate': candidate, 'construction': str(path.relative_to(HERE)),
                     'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    print(json.dumps({'case_id': CASE_ID, 'rows': rows}, indent=2))
