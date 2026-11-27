"""Attach independent stop, purpose and circumstance review to sealed Native bus sources.

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
    for name in ('native.json','site.json','designation.json','route.json','identity.json'):
        if not (attempt/name).is_file():
            raise ValueError('missing sealed original acquisition: '+name)
    value=json.loads(review.read_text())
    if (value.get('kind')!='bus_loading_stop_review' or value.get('source_class')!='original_independent_review'
            or not value.get('independent_reviewer') or not isinstance(value.get('events'),list)
            or value.get('loading_purpose') not in ('passenger','baggage','cargo_only')
            or value.get('stop_reason') not in ('ordinary','emergency')):
        raise ValueError('independent original activity, purpose and circumstance review incomplete')
    if not args.case.startswith('testing__C378132__LVMC-11-60-030-A2__bus_driver__'):
        raise ValueError('wrong exact A2 bus assignment')
    config=json.loads((attempt/'config.json').read_text())
    if config.get('selected_case_id')!=args.case:
        raise ValueError('selected case differs from sealed attempt')
    selected=config['case']
    if value['loading_purpose']!=selected['loading_purpose'] or value['stop_reason']!=selected['stop_reason']:
        raise ValueError('independent purpose/exception review differs from selected case')
    identity=json.loads((attempt/'identity.json').read_text())
    bus_id=identity['bus_id']
    if value.get('bus_id')!=bus_id:
        raise ValueError('independent review bus identity differs')
    packet=attempt/'location-source-packet.json'
    if packet.exists() or any((attempt/(name+'.json')).exists() for name in ('activity','purpose','circumstances')):
        raise ValueError('retain prior reviewed activity and source packet')
    common={'source_class':'original_independent_review','independent_reviewer':value['independent_reviewer']}
    documents={
        'activity':{**common,'kind':'bus_stop_activity_review','events':value['events']},
        'purpose':{**common,'kind':'loading_purpose_review','bus_id':bus_id,
                   'loading_purpose':value['loading_purpose'],'source_sha256':sha(review)},
        'circumstances':{**common,'kind':'stop_circumstances_review','bus_id':bus_id,
                         'stop_reason':value['stop_reason'],'source_sha256':sha(review)}}
    for name,document in documents.items():
        (attempt/(name+'.json')).write_text(json.dumps(document,indent=2,sort_keys=True)+'\n')
    refs={key:{'path':name,'sha256':sha(attempt/name)} for key,name in
          [(key,key+'.json') for key in ('site','designation','route','identity','activity','purpose','circumstances','native')]}
    source={'kind':'bus_loading_location_source_packet','case_id':args.case,'diagnostic_fixture':False,
            'source_refs':refs,**{key:selected[key] for key in ('location_kind','loading_purpose','stop_reason','bus_class')},
            'independent_activity_review_sha256':sha(review),
            'original_capture_seal_sha256':sha(attempt/'capture-seal.json')}
    packet.write_text(json.dumps(source,indent=2,sort_keys=True)+'\n')
    print('original bus activity bound to sealed acquisition: '+args.case)


if __name__=='__main__':
    main()
