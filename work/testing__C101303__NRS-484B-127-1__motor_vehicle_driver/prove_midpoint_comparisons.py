"""Prove both adjacent midpoint comparisons on 900-frame synthetic sources."""
import hashlib
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
sys.path.insert(0,str(ROOT))
from comparison_audit import audit_pair

MANIFEST=ROOT/'midpoint-promotion-ready.json'
TEMP=REPO/'.runtime-work/c101303-midpoint-comparison-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source(label):
    path=REPO/'.runtime-work/c101303-full-duration'/(label+'-positive-v1/attempt/vehicle_history.jsonl')
    receipt=json.loads((ROOT/'delivery-proofs'/label/'diagnostic-audit.json').read_text())
    if (receipt.get('frames')!=900 or receipt.get('passed') is not False
            or receipt['original_sources']['history_sha256']!=sha(path)):
        raise ValueError('Full-duration diagnostic source changed: '+label)
    return path


def main():
    manifest=json.loads(MANIFEST.read_text())
    case=next(c for c in manifest['cases'] if c['case_id'].endswith('__source_verified_midpoint'))
    bundle=json.loads((ROOT/case['construction']).read_text())
    config=json.loads(next(f['content'] for f in bundle['files'] if f['path']=='config.json'))
    if config['requested_engineering_gap_m']!=8.5:
        raise ValueError('Midpoint construction changed')
    base,closer=source('base'),source('closer')
    TEMP.mkdir(parents=True,exist_ok=True)
    midpoint=TEMP/'midpoint-projected-history.jsonl'
    rows=[]
    for line in base.read_text().splitlines():
        row=json.loads(line)
        row['lead']['body_vertices_xy_m']=[[p[0]-1.5,p[1]]
                                             for p in row['lead']['body_vertices_xy_m']]
        row['diagnostic_projection']={'scope':'synthetic CPU comparison only',
                                      'requested_gap_m':8.5,
                                      'source_sha256':sha(base),
                                      'construction_sha256':case['construction_sha256'],
                                      'physical_motion_proven':False}
        rows.append(row)
    if len(rows)!=900:
        raise ValueError('Source history is not full duration')
    midpoint.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
    results=[
        audit_pair(ROOT,'body_gap_midpoint',base,midpoint,manifest_path=MANIFEST),
        audit_pair(ROOT,'body_gap_midpoint_closer',closer,midpoint,manifest_path=MANIFEST)]
    if any(result['frames']!=900 for result in results):
        raise ValueError('Midpoint comparison lost frames')
    if not (results[0]['observed_values'][0]>results[0]['observed_values'][1]
            >results[1]['observed_values'][0]):
        raise ValueError('Synthetic midpoint body gap is not between endpoints')
    changed=[dict(row) for row in rows]
    changed[0]['surface_condition']='synthetic_tamper'
    negative=TEMP/'negative-surface.jsonl'
    negative.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in changed))
    try:
        audit_pair(ROOT,'body_gap_midpoint',base,negative,manifest_path=MANIFEST)
    except ValueError as error:
        if 'comparison surface differs unexpectedly' not in str(error):
            raise
    else:
        raise ValueError('Comparison accepted changed fixed surface')
    receipt={'format':'c101303-midpoint-synthetic-comparison-proof',
             'manifest_sha256':sha(MANIFEST),
             'construction_sha256':case['construction_sha256'],
             'source_sha256':{'base':sha(base),'closer':sha(closer),'midpoint_projection':sha(midpoint)},
             'diagnostic_only':True,'physical_motion_proven':False,
             'legal_conclusion':'unresolved','negative_fixed_surface_rejected':True,
             'comparisons':results}
    (ROOT/'midpoint-promotion-proofs/comparison-proof.json').write_text(json.dumps(receipt,indent=2)+'\n')
    print('900-frame midpoint comparisons and altered-surface rejection passed')


if __name__=='__main__':
    main()
