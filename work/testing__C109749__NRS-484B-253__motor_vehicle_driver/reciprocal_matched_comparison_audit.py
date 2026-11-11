"""Independent fixed-condition comparison for the matched reciprocal drafts.

The software diagnostic can prove identical authored inputs and source joins.
It cannot establish physical motion or a legal right-of-way conclusion.
"""

import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

FOLDER = Path(__file__).resolve().parent
POSITIVE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_yield_matched'
NEGATIVE = 'testing__C109749__NRS-484B-253__motor_vehicle_driver__reciprocal_no_yield'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing fixed comparison source: ' + path.name)
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing fixed comparison source: ' + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def normalized_config(config):
    config = dict(config)
    config.pop('selected_case_id', None)
    config.pop('supported_case_ids', None)
    return config


def normalized_runner(source, case, *, positive):
    source = source.replace(case, '<CASE>')
    source = source.replace('Matched yield candidate requires', 'Matched candidate requires')
    source = source.replace('No-yield entry candidate requires', 'Matched candidate requires')
    if positive:
        policy = "later_target = (0.0 if command['state'] in ('turn','complete')\n                                        else config['reciprocal_approach_speed_mps'])  # matched braking policy"
    else:
        policy = "later_target = config['reciprocal_approach_speed_mps']  # authored no-stop entry policy; observed entry is checked after capture"
    if source.count(policy) != 1:
        raise ValueError('Expected reciprocal policy code not found exactly once')
    return source.replace(policy, 'later_target = <DECLARED_RECIPROCAL_POLICY>')


def compare_histories(positive_rows, negative_rows, polygon_xy):
    if len(positive_rows) != len(negative_rows) or len(positive_rows) < 9:
        raise ValueError('Matched original history length differs')
    turn = next((i for i, row in enumerate(positive_rows)
                 if abs((row['ego_heading_deg']-positive_rows[0]['ego_heading_deg']+180)%360-180)>=15), None)
    if turn is None:
        raise ValueError('Positive subject turn missing')
    polygon = Polygon(polygon_xy)
    if not polygon.is_valid or polygon.is_empty:
        raise ValueError('Fixed junction geometry invalid')
    body = lambda row, role: MultiPoint(row[role]['body_vertices_xy_m']).convex_hull
    for i, (left, right) in enumerate(zip(positive_rows, negative_rows)):
        for key in ('frame','time_s','ego','oncoming','ego_heading_deg','ego_left_indicator'):
            if left[key] != right[key]:
                raise ValueError(f'Fixed {key} trajectory differs at sample {i}')
        if i < turn and left['reciprocal'] != right['reciprocal']:
            raise ValueError(f'Fixed pre-turn reciprocal trajectory differs at sample {i}')
    ego_exit = next((i for i in range(turn,len(positive_rows))
                     if not polygon.intersects(body(positive_rows[i],'ego'))),None)
    if ego_exit is None:
        raise ValueError('Matched subject exit missing')
    stopped = next((i for i in range(turn,ego_exit)
                    if not polygon.intersects(body(positive_rows[i],'reciprocal'))
                    and sum(v*v for v in positive_rows[i]['reciprocal']['velocity_xy_mps']) < 0.01),None)
    entered = next((i for i in range(turn,ego_exit)
                    if polygon.intersects(body(negative_rows[i],'reciprocal'))
                    and sum(v*v for v in negative_rows[i]['reciprocal']['velocity_xy_mps']) > 0.25),None)
    if stopped is None or entered is None:
        raise ValueError('Declared stopped-outside versus moving-entry difference absent')
    return {'frames':len(positive_rows),'fixed_samples':len(positive_rows),
            'turn_frame':positive_rows[turn]['frame'],'ego_exit_frame':positive_rows[ego_exit]['frame'],
            'positive_stop_frame':positive_rows[stopped]['frame'],
            'negative_entry_frame':negative_rows[entered]['frame']}


def compare(positive, negative, output, *, diagnostic_selftest=False):
    positive, negative, output = Path(positive).resolve(), Path(negative).resolve(), Path(output)
    if positive == negative:
        raise ValueError('Two independent exact attempts required')
    attempts = ((positive,POSITIVE,True),(negative,NEGATIVE,False))
    constructions = []
    for root,case,is_positive in attempts:
        seal = read(root/'capture-seal.json')
        for name in ('config.json','intersection_geometry.json','interaction_history.jsonl','video_frames.jsonl'):
            if seal.get('sources',{}).get(name) != sha(root/name):
                raise ValueError('Fixed comparison original is unsealed or stale: '+name)
        config = read(root/'config.json')
        audit = read(root/'diagnostic-audit.json' if diagnostic_selftest else root/'delivery-audit.json')
        if (config.get('selected_case_id')!=case or audit.get('case_id')!=case or
                audit.get('software_checks_passed') is not True or
                audit.get('diagnostic_fixture') is not diagnostic_selftest or
                audit.get('passed') is not (not diagnostic_selftest) or
                audit.get('physical_acceptance_claimed') is not False or
                audit.get('source_result_sha256')!=sha(root/'result.json') or
                audit.get('auditor_sha256')!=sha(FOLDER/'cases'/('reciprocal_yield_matched' if is_positive else 'reciprocal_no_yield')/'delivery_audit.py') or
                audit.get('original_sources',{}).get('history_sha256')!=sha(root/'interaction_history.jsonl')):
            raise ValueError('Independent exact delivery audit missing or stale')
        bundle = read(FOLDER/'cases'/('reciprocal_yield_matched' if is_positive else 'reciprocal_no_yield')/'construction.json')
        files = {item['path']:item['content'] for item in bundle['files']}
        if json.loads(files['config.json']) != config:
            raise ValueError('Sealed config differs from current construction')
        constructions.append(files)
    left_files,right_files = constructions
    for name in ('construction.py','controller.py','capture_sources.py','native_scene.py',
                 'camera_setup.py','camera_encoder.py','measurements.py'):
        if left_files[name] != right_files[name]:
            raise ValueError('Fixed construction code differs: '+name)
    if normalized_runner(left_files['runner.py'],POSITIVE,positive=True) != normalized_runner(right_files['runner.py'],NEGATIVE,positive=False):
        raise ValueError('Runner differs beyond declared later-opposing policy')
    left_config,right_config = read(positive/'config.json'),read(negative/'config.json')
    if normalized_config(left_config) != normalized_config(right_config):
        raise ValueError('Fixed configuration differs beyond exact case identity')
    if (sha(positive/'intersection_geometry.json')!=sha(negative/'intersection_geometry.json') or
            sha(positive/'video_frames.jsonl')!=sha(negative/'video_frames.jsonl')):
        raise ValueError('Fixed geometry or frame map differs')
    sequence = compare_histories(rows(positive/'interaction_history.jsonl'),
                                 rows(negative/'interaction_history.jsonl'),
                                 read(positive/'intersection_geometry.json')['intersection_polygon_xy_m'])
    receipt = {'format':'worker-reciprocal-matched-comparison-diagnostic' if diagnostic_selftest else 'worker-reciprocal-matched-comparison',
               'passed':not diagnostic_selftest,'software_checks_passed':True,
               'diagnostic_fixture':diagnostic_selftest,'physical_acceptance_claimed':False,
               'legal_verdict_asserted':False,'positive_case_id':POSITIVE,'negative_case_id':NEGATIVE,
               'declared_variable':'later opposing target becomes zero at subject turn onset versus continued approach',
               'fixed_conditions':['construction helpers','camera plan','configuration excluding case identity',
                                   'junction geometry','900-frame map','all subject and initial opposing motion',
                                   'later opposing motion before turn'],
               'sequence':sequence,'source_sha256':{'positive_history':sha(positive/'interaction_history.jsonl'),
                  'negative_history':sha(negative/'interaction_history.jsonl'),
                  'positive_audit':sha(positive/('diagnostic-audit.json' if diagnostic_selftest else 'delivery-audit.json')),
                  'negative_audit':sha(negative/('diagnostic-audit.json' if diagnostic_selftest else 'delivery-audit.json'))},
               'auditor_sha256':sha(__file__)}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--positive',required=True)
    p.add_argument('--negative',required=True)
    p.add_argument('--output',required=True)
    p.add_argument('--diagnostic-selftest',action='store_true')
    a=p.parse_args()
    print(json.dumps(compare(a.positive,a.negative,a.output,diagnostic_selftest=a.diagnostic_selftest)))
