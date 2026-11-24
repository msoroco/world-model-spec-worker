"""Independently recompute the controlled opening/barrier source contrast."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rectangle_area(body,bounds):
    x=[point[0] for point in body]
    y=[point[1] for point in body]
    return max(0,min(max(x),bounds[2])-max(min(x),bounds[0])) * \
           max(0,min(max(y),bounds[3])-max(min(y),bounds[1]))


def main():
    proof_path=HERE/'median-crossing-proof.json'
    proof=json.loads(proof_path.read_text())
    if proof['selected'] or proof['accepted'] or len(proof['negative_errors'])!=2:
        raise ValueError('Diagnostic proof scope differs')
    law=json.loads((ROOT/'inputs'/HERE.name/'assignment.json').read_text())['law']['text']
    if 'right-hand roadway' not in law or 'except through an opening' not in law or \
            'established by a public authority' not in law:
        raise ValueError('Original statutory alternatives differ')
    data={}
    for suffix in ('probe_a','probe_b'):
        ref=proof['case_sources'][suffix]
        folder=ROOT/ref['folder']
        manifest=json.loads((folder/'sources.json').read_text())
        if sha(folder/'sources.json')!=ref['manifest_sha256'] or \
                manifest['source_kind']!='synthetic_cpu_geometry_diagnostic':
            raise ValueError('Independent source scope or manifest hash differs')
        for name,digest in manifest['sha256'].items():
            if sha(folder/name)!=digest:raise ValueError('Raw source hash differs')
        geometry=json.loads((folder/'geometry.json').read_text())
        if geometry['public_authority_establishment_verified'] is not False:
            raise ValueError('Fixture asserts unsupported public authority')
        rows=[json.loads(line) for line in (folder/'body.jsonl').read_text().splitlines()]
        if len(rows)!=600:raise ValueError('Full 600-frame source required')
        opening=barrier=median=0
        for index,row in enumerate(rows):
            if row['native_frame']!=1000+index or row['video_frame']!=index or \
                    abs(row['time_s']-index/20)>1e-6:
                raise ValueError('Independent 20 Hz join differs')
            body=row['native_body_xy_m']
            m=rectangle_area(body,geometry['median_bounds_m'])
            o=rectangle_area(body,geometry['opening_bounds_m'])
            b=sum(rectangle_area(body,bounds) for bounds in geometry['barrier_bounds_m'])
            if abs(m-o-b)>1e-8:raise ValueError('Independent median partition differs')
            median+=m>0;opening+=o>0;barrier+=b>0
        measured=proof['observed'][suffix]
        if (measured['median_occupied_frames'],measured['opening_occupied_frames'],
            measured['barrier_occupied_frames'])!=(median,opening,barrier):
            raise ValueError('Source and measurement proof differ')
        if any(not message for message in proof['negative_errors'][suffix].values()):
            raise ValueError('Missing negative diagnostic')
        data[suffix]={'rows':len(rows),'median_frames':median,
                      'opening_frames':opening,'barrier_frames':barrier,
                      'source_sha256':manifest['sha256']}
        data[suffix]['raw_rows']=rows
    first=data['probe_a'].pop('raw_rows')
    second=data['probe_b'].pop('raw_rows')
    for a,b in zip(first,second):
        for key in ('native_frame','video_frame','time_s','speed_mps','source_scope'):
            if a[key]!=b[key]:raise ValueError('Controlled timing or motion differs')
        if any(abs((right[0]-left[0])-12)>1e-8 or abs(right[1]-left[1])>1e-8
               for left,right in zip(a['native_body_xy_m'],b['native_body_xy_m'])):
            raise ValueError('Comparison changes more than crossing x translation')
    if data['probe_a']['barrier_frames']!=0 or data['probe_b']['opening_frames']!=0 or \
            data['probe_a']['median_frames']!=data['probe_b']['median_frames']:
        raise ValueError('Controlled opening/barrier contrast differs')
    audit={'format':'c124163-independent-median-crossing-audit-v1','passed':True,
           'proof_sha256':sha(proof_path),'law_input_sha256':sha(ROOT/'inputs'/HERE.name/'assignment.json'),
           'cases':data,'fixed_y_time_speed_and_body_shape':True,
           'sole_difference':'12 m x translation',
           'selected':False,'accepted':False,
           'authority_verified':False,'physical_native_verified':False}
    output=HERE/'median-crossing-audit.json'
    output.write_text(json.dumps(audit,indent=2)+'\n')
    print(json.dumps({'audit_sha256':sha(output),'passed':True}))


if __name__=='__main__':main()
