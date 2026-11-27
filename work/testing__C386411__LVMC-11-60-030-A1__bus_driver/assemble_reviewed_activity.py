"""Attach independently reviewed activity to one immutable Native bus attempt.

The review is created outside the package from original camera pixels and Native
history. This tool only verifies its signed hash and binds source references.
"""
import argparse
import hashlib
import json
from pathlib import Path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',type=Path,required=True)
    parser.add_argument('--review',type=Path,required=True)
    parser.add_argument('--case',required=True)
    args=parser.parse_args()
    attempt=args.attempt.resolve()
    review=args.review.resolve()
    sidecar=review.with_suffix(review.suffix+'.sha256')
    if not sidecar.is_file() or sidecar.read_text().strip()!=sha(review):
        raise ValueError('independent activity review SHA256 sidecar differs')
    if not (attempt/'capture-seal.json').is_file() or not (attempt/'native-exit.json').is_file():
        raise ValueError('Native acquisition and owner process must close first')
    for name in ('native.json','site.json','designation.json','identity.json'):
        if not (attempt/name).is_file():
            raise ValueError('missing sealed original acquisition: '+name)
    value=json.loads(review.read_text())
    if (value.get('kind')!='bus_activity_review' or value.get('source_class')!='original_independent_review'
            or not value.get('independent_reviewer') or not value.get('events')
            or value.get('conduct') not in ('stand','park')):
        raise ValueError('independent original activity review incomplete')
    if not args.case.startswith('testing__C386411__LVMC-11-60-030-A1__bus_driver__'):
        raise ValueError('wrong exact bus location assignment')
    suffix=args.case.split('__')[-1]
    if value['conduct']!=suffix.split('_')[0]:
        raise ValueError('activity review conduct differs from selected exact case')
    target=attempt/'activity.json'
    packet=attempt/'location-source-packet.json'
    if target.exists() or packet.exists():
        raise ValueError('retain prior reviewed activity and source packet')
    target.write_bytes(review.read_bytes())
    refs={key:{'path':name,'sha256':sha(attempt/name)} for key,name in
          [('site','site.json'),('designation','designation.json'),('identity','identity.json'),
           ('activity','activity.json'),('native','native.json')]}
    source={'kind':'bus_location_source_packet','case_id':args.case,'diagnostic_fixture':False,
            'source_refs':refs,'location_relation':suffix.split('_')[-1],
            'independent_activity_review_sha256':sha(review),
            'original_capture_seal_sha256':sha(attempt/'capture-seal.json')}
    packet.write_text(json.dumps(source,indent=2,sort_keys=True)+'\n')
    print('original bus activity bound to sealed acquisition: '+args.case)


if __name__=='__main__':
    main()
