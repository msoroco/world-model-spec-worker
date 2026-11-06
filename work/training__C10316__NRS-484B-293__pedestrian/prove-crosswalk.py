"""Build two unselected, 12-second synthetic crosswalk source fixtures and negatives."""
import json
from pathlib import Path
import shutil
from native.measure_crosswalk import measure, sha, FRAMES, RATE_HZ

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT/'.runtime-work/c10316-crosswalk-synthetic'


def dump(path, value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def rows_for(lateral):
    rows=[]
    for frame in range(FRAMES):
        x=-4+8*frame/(FRAMES-1)
        y=lateral
        rows.append({'native_frame':frame,'time_s':round(frame/RATE_HZ,6),
                     'crosswalk_id':'C10316-authored-alley-crosswalk',
                     'pedestrian_xy_m':[x,y], 'pedestrian_forward_xy':[1,0],
                     'speed_mps':8*RATE_HZ/(FRAMES-1),
                     'pedestrian_footprint_xy_m':[[x-.12,y-.12],[x+.12,y-.12],
                                                  [x+.12,y+.12],[x-.12,y+.12]]})
    return rows


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))


def reject(label,rows,context,error):
    place=OUT/('negative-'+label)
    place.mkdir()
    if rows is not None:
        write_rows(place/'native_samples.jsonl',rows)
    if context is not None:
        dump(place/'crosswalk-context.json',context)
    try:
        measure(place/'native_samples.jsonl',place/'crosswalk-context.json')
    except ValueError as exc:
        assert error in str(exc), (label,str(exc))
        return {'label':label,'expected_error':error,'actual_error':str(exc)}
    raise AssertionError(label+' unexpectedly accepted')


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    context={'source_kind':'synthetic_scene_request',
             'crosswalk_id':'C10316-authored-alley-crosswalk',
             'crosswalk_center_xy_m':[0,0],
             'crosswalk_passage_forward_xy':[1,0],
             'crosswalk_length_m':4,'crosswalk_width_m':3,
             'practicability_facts':[{'name':'right_half_obstruction','requested':'none',
                                      'observed':None},
                                     {'name':'oncoming_pedestrians','requested':'none',
                                      'observed':None}]}
    reports=[]
    for label,lateral,half in (('reference',-.65,'right'),('contrast',.65,'left')):
        place=OUT/label; place.mkdir()
        write_rows(place/'native_samples.jsonl',rows_for(lateral))
        dump(place/'crosswalk-context.json',context)
        report=measure(place/'native_samples.jsonl',place/'crosswalk-context.json')
        assert report['observed_half']==half and report['crosswalk_frames'] >= 100
        assert report['practicability_verified'] is False and report['legal_verdict_claimed'] is False
        dump(place/'measurement.json',report)
        reports.append({'case_id':'training__C10316__NRS-484B-293__pedestrian__'+label,
                        'source_directory':str(place.relative_to(ROOT)),
                        'measurement_sha256':sha(place/'measurement.json'),
                        'observed_half':half,
                        'crosswalk_frames':report['crosswalk_frames']})
    base=rows_for(-.65)
    wrong_heading=[dict(r) for r in base]
    wrong_heading[100]['pedestrian_forward_xy']=[-1,0]
    straddle=rows_for(0)
    misses=rows_for(-2.5)
    unproven_native={**context,'source_kind':'native_observation'}
    negatives=[
        reject('missing-context',base,None,'Missing required source: crosswalk-context.json'),
        reject('short-source',base[:100],context,'Full 12-second original crossing source required'),
        reject('wrong-heading',wrong_heading,context,'Original pedestrian heading differs'),
        reject('no-traverse',misses,context,'Original pedestrian did not traverse'),
        reject('native-no-provenance',base,unproven_native,'Native crosswalk context lacks map/frame provenance'),
    ]
    summary={'format':'c10316-unselected-crosswalk-synthetic-proof-v1',
             'source_kind':'synthetic_scene_request','selected_cases':0,
             'comparison_variable':'pedestrian_lateral_crosswalk_half',
             'reports':reports,'negative_checks':negatives}
    dump(HERE/'draft-crosswalk-proof.json',summary)
    print(json.dumps({'synthetic_positives':len(reports),'negative_checks':len(negatives),
                      'reference_half':reports[0]['observed_half'],
                      'contrast_half':reports[1]['observed_half'],
                      'selected_cases':0},sort_keys=True))


if __name__=='__main__':
    main()
