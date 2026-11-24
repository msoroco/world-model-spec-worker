"""Audit selected current-runtime saved exit-side comparison and source rows."""
import hashlib
import json
import math
from pathlib import Path

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):return [json.loads(line) for line in Path(path).read_text().splitlines()]


def run():
    manifest=json.loads((HERE/'execution-manifest.json').read_text())
    cases=manifest['cases']
    if len(cases)!=2:raise ValueError('Expected exact selected pair')
    sources=[];reports=[];motion=[]
    for case in cases:
        suffix=case['case_id'].rsplit('__',1)[-1]
        source=HERE/'current-fixture'/suffix
        processing=json.loads((HERE/'current-public'/(suffix+'-primary-processing.json')).read_text())
        report=json.loads((Path(processing['analysis_directory'])/'analysis-report.json').read_text())
        if (report['case_id']!=case['case_id'] or report['candidate_id']!='primary'
                or report['acquisition_provenance']['source_kind']!='synthetic_fixture'
                or report['acquisition_provenance']['native_executed'] is not False
                or report['original_joins']['frames']!=480
                or not all(n==480 for n in report['video_frames'].values())
                or not processing['passed'] or not processing['recorded_only']
                or not processing['originals_preserved'] or processing['physical_acceptance_claimed']):
            raise ValueError('Current selected saved source not bound')
        sources.append(source);reports.append(report);motion.append(rows(source/'native_samples.jsonl'))
    if (sources[0]/'road_geometry.json').read_bytes()!=(sources[1]/'road_geometry.json').read_bytes():
        raise ValueError('Road geometry differs')
    if len(motion[0])!=len(motion[1]) or len(motion[0])!=480:
        raise ValueError('Source lengths differ')
    for index,(first,second) in enumerate(zip(*motion)):
        for key in ('native_frame','time_s','native_forward_xy'):
            if first[key]!=second[key]:raise ValueError('Comparison changed '+key)
        if not math.isclose(first['native_center_xy_m'][1],second['native_center_xy_m'][1],abs_tol=1e-9):
            raise ValueError('Comparison changed longitudinal destination motion')
        expected=0 if index<160 else -3.5*(index-160)/159 if index<320 else -3.5
        if not math.isclose(second['native_center_xy_m'][0]-first['native_center_xy_m'][0],expected,abs_tol=1e-9):
            raise ValueError('Unexpected exit lateral difference')
        if index<160 and first!=second:raise ValueError('Approach changed before divergence')
    measured=[r['measurements']['destination_exit_geometry']['value'] for r in reports]
    if [v['geometric_side'] for v in measured]!=['right','left']:
        raise ValueError('Saved exit-side measurement changed')
    for value in measured:
        entry=value['first_intersection_entry_time_bracket_s']
        departure=value['first_full_body_exit_time_bracket_s']
        if not value['full_body_exit_observed'] or not value['intersection_entry_observed'] or not entry[0]<entry[1]<=departure[0]<departure[1]:
            raise ValueError('Entry/turn/exit order changed')
    return {'format':'c329610-current-exit-saved-comparison',
            'case_ids':[c['case_id'] for c in cases],
            'runtime_manifest_sha256':manifest['runtime_manifest_sha256'],
            'frames_per_case':480,'road_geometry_sha256':sha(sources[0]/'road_geometry.json'),
            'native_sample_sha256':[sha(s/'native_samples.jsonl') for s in sources],
            'measured_full_body_exit_sides':['right','left'],
            'only_deliberate_difference':'destination exit lateral path',
            'diagnostic_only':True,'original_native_observed':False,
            'physical_acceptance':False,'legal_verdict':None}


if __name__=='__main__':print(json.dumps(run(),sort_keys=True))
