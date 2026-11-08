"""Synthetic saved exception fact coverage with source and status negatives."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
from measure_exception import FACTS,measure

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast');CANDIDATES=('primary','fallback1','fallback2','fallback3')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def rejected(folder,path,packet):
    path.write_text(json.dumps(packet)+'\n')
    try:measure(folder,path)
    except (ValueError,TypeError,KeyError):return True
    raise AssertionError('Altered exception packet accepted')


def prove():
    positives=[];negatives=[]
    for case in CASES:
        for candidate in CANDIDATES:
            folder=HERE/'saved-fixtures'/case/candidate
            doc=folder/'authority/synthetic-exception-source.json'
            doc.parent.mkdir(exist_ok=True)
            doc.write_text(json.dumps({'source_kind':'synthetic_cpu',
                                       'note':'Diagnostic reported facts, no actor or legal authority'},indent=2)+'\n')
            records={name:{'value':False,'document_path':'authority/synthetic-exception-source.json',
                           'document_sha256':sha(doc),'citation':'synthetic diagnostic only',
                           'reviewed':False} for name in FACTS}
            packet={'format':'c422978-heavy-exception-evidence-v1',
                    'law_id':'NRS-484B-117-1','source_kind':'synthetic_cpu',
                    'native_capture_report_sha256':sha(folder/'native-capture-report.json'),
                    'native_map_readback_sha256':sha(folder/'native-map-readback.json'),
                    'review_status':'pending_independent_review','legal_verdict':None,
                    'facts':records}
            path=folder/'exception-evidence.json';path.write_text(json.dumps(packet,indent=2)+'\n')
            output=measure(folder,path)
            if output['reported_exception_pattern'] or output['exception_applies'] is not None or output['legal_verdict'] is not None:
                raise AssertionError('Synthetic exception negative pattern differs')
            positives.append({'case':case,'candidate':candidate,'measurement':output})
            with tempfile.TemporaryDirectory(dir=HERE) as temporary:
                bad_path=Path(temporary)/'packet.json'
                for name,alter in (
                    ('capture_binding',lambda x:x.update(native_capture_report_sha256='0'*64)),
                    ('map_binding',lambda x:x.update(native_map_readback_sha256='0'*64)),
                    ('review_claim',lambda x:x.update(review_status='reviewed')),
                    ('fact_coverage',lambda x:x['facts'].pop('solely_electric')),
                    ('document_hash',lambda x:x['facts']['solely_electric'].update(document_sha256='0'*64)),
                    ('invalid_fact',lambda x:x['facts']['solely_electric'].update(value='false'))):
                    bad=copy.deepcopy(packet);alter(bad)
                    negatives.append({'case':case,'candidate':candidate,'mutation':name,
                                      'rejected':rejected(folder,bad_path,bad)})
                candidate_packet=copy.deepcopy(packet)
                for name in ('solely_electric','designed_three_wheels',
                             'authorized_emergency_vehicle','emergency_operation_at_event'):
                    candidate_packet['facts'][name]['value']=True
                bad_path.write_text(json.dumps(candidate_packet)+'\n')
                candidate_result=measure(folder,bad_path)
                if not candidate_result['reported_exception_pattern'] or candidate_result['exception_applies'] is not None or candidate_result['legal_verdict'] is not None:
                    raise AssertionError('Reported synthetic candidate pattern lost pending scope')
    proof={'format':'c422978-heavy-exception-cpu-proof-v1',
           'processor_sha256':sha(HERE/'measure_exception.py'),
           'positives':positives,'negatives':negatives,
           'synthetic_reported_pattern_probes':8,
           'original_authority_reviewed':False,'delivery_ready':False}
    (HERE/'exception-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
    return proof

if __name__=='__main__':
    r=prove();print(json.dumps({'positives':len(r['positives']),'negatives':len(r['negatives']),
                               'pattern_probes':r['synthetic_reported_pattern_probes']}))
