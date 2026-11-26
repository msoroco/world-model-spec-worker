"""Independent original-source comparison of parking boundaries and exceptions."""
import argparse
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
GROUPS={
    'curb_boundary':('right_16_parked','right_18_parked','right_20_parked'),
    'rest_mode':('right_18_parked','right_18_stopped'),
    'angle_dot_context':('angle_ordinary','angle_dot'),
}
CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):return json.loads(Path(path).read_text())


def read_rows(path):
    rows=[json.loads(line) for line in Path(path).read_text().splitlines()]
    if len(rows)!=600:raise ValueError('Comparison lacks 600 original frames')
    return rows


def requests(group):
    values=[]
    for suffix in GROUPS[group]:
        construction=read(HERE/'native/bundles'/suffix/'construction.json')
        content=next(f['content'] for f in construction['files'] if f['path']=='request.json')
        values.append(json.loads(content))
    return values


def verify_requests(group,values):
    first=values[0]
    expected={'curb_boundary':{'case','requested_gap_in','requested_center_xy_m'},
              'rest_mode':{'case','rest_mode'},
              'angle_dot_context':{'case','parking_kind','authority_request'}}[group]
    for item in values[1:]:
        changed={name for name in set(first)|set(item) if first.get(name)!=item.get(name)}
        if changed!=expected:
            raise ValueError('Uncontrolled authored parking comparison: '+group+' '+str(changed))
        if item['frames']!=600 or item['cameras']!=first['cameras'] or item['source_map']!=first['source_map']:
            raise ValueError('Fixed road/capture changed')
    return True


def verify_source_rows(group,groups):
    first=groups[0]
    for rows in groups:
        if len(rows)!=600:raise ValueError('Incomplete original parking source')
        for i,row in enumerate(rows):
            if row.get('video_frame')!=i or row.get('ego',{}).get('body_xyz_m') is None:
                raise ValueError('Original body/frame source missing')
            if row.get('time_s')!=i/20:
                raise ValueError('Source time changed')
    for rows in groups[1:]:
        for a,b in zip(first,rows):
            ae,be=a['ego'],b['ego']
            if abs(ae['center_xyz_m'][0]-be['center_xyz_m'][0])>.25 or abs(ae['center_xyz_m'][2]-be['center_xyz_m'][2])>.25:
                raise ValueError('Fixed longitudinal/vertical trajectory changed')
            if abs(ae['speed_mps']-be['speed_mps'])>.25:
                raise ValueError('Fixed approach speed changed')
            if group!='curb_boundary' and abs(ae['center_xyz_m'][1]-be['center_xyz_m'][1])>.25:
                raise ValueError('Fixed lateral position changed')
            if group=='angle_dot_context' and abs(ae['yaw_deg']-be['yaw_deg'])>2:
                raise ValueError('Angle changed outside DOT context')
            if group=='rest_mode' and a['rest_mode_request']==b['rest_mode_request']:
                raise ValueError('Stopped/parked request did not differ')
    return True


def audit(group,folders,output):
    if group not in GROUPS or len(folders)!=len(GROUPS[group]):
        raise ValueError('Exact comparison membership differs')
    output=Path(output)
    if output.exists():raise ValueError('Retain previous comparison audit')
    verify_requests(group,requests(group))
    rows=[];metrics=[]
    for suffix,folder in zip(GROUPS[group],map(Path,folders)):
        result=read(folder/'result.json');metric=result.get('measured_values',{})
        if result.get('case_id')!=HERE.name+'__'+suffix or result.get('provenance_kind')!='native' or metric.get('diagnostic_fixture') is not False or metric.get('original_native_observed') is not True:
            raise ValueError('Original Native comparison source required')
        if not metric.get('source_review_sha256') or sha(folder/'source-review.json')!=metric['source_review_sha256']:
            raise ValueError('Original curb/wheel/authority source review missing')
        if not result.get('maneuver_completed') or result.get('physical_checks',{}).get('maneuver',{}).get('status')!='met':
            raise ValueError('Original physical parking completion missing')
        rows.append(read_rows(folder/'native-parking.jsonl'));metrics.append(metric)
    verify_source_rows(group,rows)
    if group=='curb_boundary':
        if [round(m['front_wheel_gap_in_max']) for m in metrics]!=[16,18,20]:
            raise ValueError('Original 16/18/20-inch measurements absent')
    if group=='angle_dot_context':
        if [m['parking_kind'] for m in metrics]!=['angle_ordinary','angle_dot']:
            raise ValueError('DOT angle context contrast absent')
        if metrics[1]['administrative_authority'].get('dot_width_determination_status')!='verified':
            raise ValueError('DOT width determination absent')
    value={'format':'worker-parking-comparison-audit','passed':True,'comparison':group,
        'case_ids':[HERE.name+'__'+s for s in GROUPS[group]],
        'source_result_sha256':[sha(Path(f)/'result.json') for f in folders],
        'fixed_conditions':['one-way road','adjacent curbs','vehicle blueprint',
                            '600-frame timeline','four source cameras'],
        'deliberate_differences':{'curb_boundary':['requested wheel-to-curb gap'],
            'rest_mode':['stopped versus parked rest request'],
            'angle_dot_context':['DOT designation and width determination']}[group],
        'physical_or_legal_acceptance_claimed_by_fixture':False}
    output.write_text(json.dumps(value,indent=2)+'\n')
    return value


def selftest(group,negative):
    verify_requests(group,requests(group))
    rows=[read_rows(HERE/'native/diagnostic'/suffix/'native-parking.jsonl') for suffix in GROUPS[group]]
    if negative:
        rows=copy.deepcopy(rows)
        rows[-1][300]['ego']['center_xyz_m'][0]+=3
        verify_source_rows(group,rows)
        raise AssertionError('Changed fixed trajectory accepted')
    verify_source_rows(group,rows)
    print(json.dumps({'format':'worker-parking-comparison-selftest','passed':True,
        'comparison':group,'case_ids':[HERE.name+'__'+s for s in GROUPS[group]],
        'physical_or_legal_acceptance_claimed':False}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--comparison',choices=GROUPS,required=True)
    parser.add_argument('--self-test',action='store_true');parser.add_argument('--negative',action='store_true')
    parser.add_argument('--attempt',action='append');parser.add_argument('--output')
    args=parser.parse_args()
    selftest(args.comparison,args.negative) if args.self_test else audit(args.comparison,args.attempt,args.output)
