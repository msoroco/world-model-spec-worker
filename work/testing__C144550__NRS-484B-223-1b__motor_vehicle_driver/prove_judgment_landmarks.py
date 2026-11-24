"""Bind judgment grid landmarks to the five exact original-frame CPU sources."""
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from lane_change_measurements import analyze

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = ('left_signal_before_clear_gap', 'left_signal_late_clear_gap',
         'left_wrong_signal_clear_gap', 'left_signal_before_close_gap',
         'right_signal_before_clear_gap')
SOURCE_NAMES = ('lane_context.json', 'lane_history.jsonl', 'video_frames.jsonl')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(name, manifest):
    entry = next(row for row in manifest['cases'] if row['case_id'] == HERE.name + '__' + name)
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    sources = {row['path']:row for row in recipe['sources']}
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work', prefix='c144550-grid-') as temporary:
        attempt = Path(temporary)
        for source_name in SOURCE_NAMES:
            source = ROOT / sources[source_name]['source']
            if sha(source) != sources[source_name]['sha256']:
                raise ValueError('Recipe source hash changed: ' + name + '/' + source_name)
            shutil.copyfile(source, attempt / source_name)
        observation = analyze(attempt)
        departure = observation['first_body_leaves_lane']['frame']
        signal = observation['first_appropriate_signal']
        movement = next(row for row in observation['samples'] if row['frame'] == departure)
        if len(observation['samples']) != 900:
            raise ValueError('Original 900-frame grid source incomplete')
        return {'case_id':entry['case_id'], 'recipe_sha256':sha(ROOT / entry['fixture_recipe']),
                'source_sha256':{key:sources[key]['sha256'] for key in SOURCE_NAMES},
                'departure_frame':departure,
                'appropriate_signal_frame':None if signal is None else signal['frame'],
                'signal_lead_frames':None if signal is None else departure - signal['frame'],
                'indicator_at_departure':movement['indicator'],
                'nearest_target_body_gap_m':movement['nearest_target_body_longitudinal_gap_m'],
                'lane_context':json.loads((attempt / 'lane_context.json').read_text())}


def prove():
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    points = {name:inspect(name,manifest) for name in NAMES}
    before, late, wrong, close, right = [points[name] for name in NAMES]
    if ([before['signal_lead_frames'],late['signal_lead_frames']] != [1,-1] or
        before['departure_frame'] != late['departure_frame'] or
        not (before['nearest_target_body_gap_m'] ==
             late['nearest_target_body_gap_m'] == 8.0) or
        wrong['appropriate_signal_frame'] is not None or
        wrong['indicator_at_departure'] != 'right'):
        raise ValueError('Signal landmarks or fixed gap differ')
    if ([close['nearest_target_body_gap_m'],before['nearest_target_body_gap_m']] != [3.0,8.0] or
        close['signal_lead_frames'] != before['signal_lead_frames'] or
        close['departure_frame'] != before['departure_frame']):
        raise ValueError('Gap landmarks or fixed signal differ')
    for name in NAMES:
        points[name].pop('lane_context')
    zero = json.loads((HERE / 'zero-signal-boundary-proof.json').read_text())
    if (zero['signal_lead_frames'] != 0 or zero['source_frame_count'] != 900 or
            zero['first_body_departure_frame'] != before['departure_frame']):
        raise ValueError('Synthetic zero-frame source probe differs from fixed signal grid')
    for source in zero['changed_sources'].values():
        if sha(ROOT / source['returned_source']) != source['zero_sha256']:
            raise ValueError('Synthetic zero-frame source changed')
    return {'format':'worker-c144550-judgment-grid-landmarks',
            'signal_lead_frames':[-1,0,1],
            'signal_boundary_zero_frame_constructed':True,
            'zero_boundary_probe_sha256':sha(HERE / 'zero-signal-boundary-proof.json'),
            'gap_at_movement_m':[3.0,8.0],
            'points':points,
            'scope':'Synthetic 900-frame original-source landmarks; zero is a CPU probe pending exact-case integration; no legal threshold',
            'physical_acceptance_claimed':False,
            'legal_acceptance_claimed':False}


if __name__ == '__main__':
    report = prove()
    (HERE / 'judgment-grid-landmarks.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'signal_lead_frames':report['signal_lead_frames'],
                      'gap_at_movement_m':report['gap_at_movement_m'],
                      'zero_signal_boundary_constructed':True},sort_keys=True))
