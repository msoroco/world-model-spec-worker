"""Independent source and coverage audit of reported exception fact packets."""
import hashlib
import json
from pathlib import Path
from measure_exception import measure

HERE=Path(__file__).resolve().parent
CASES=('reference','contrast');CANDIDATES=('primary','fallback1','fallback2','fallback3')
FACTS=('solely_electric','designed_three_wheels','authorized_emergency_vehicle',
       'emergency_operation_at_event','law_enforcement_officer_or_employee',
       'law_enforcement_official_duty_at_event','security_guard_under_definition',
       'security_guard_official_duty_at_event')
MUTATIONS=('capture_binding','map_binding','review_claim','fact_coverage','document_hash','invalid_fact')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def audit():
    proof=json.loads((HERE/'exception-proof.json').read_text())
    if proof['processor_sha256']!=sha(HERE/'measure_exception.py') or proof['synthetic_reported_pattern_probes']!=8 or proof['original_authority_reviewed'] or proof['delivery_ready']:
        raise ValueError('Exception proof code or scope differs')
    positives={(row['case'],row['candidate']):row['measurement'] for row in proof['positives']}
    negatives={(row['case'],row['candidate'],row['mutation']) for row in proof['negatives'] if row['rejected'] is True}
    expected={(case,candidate) for case in CASES for candidate in CANDIDATES}
    if set(positives)!=expected or negatives!={(case,candidate,mutation) for case,candidate in expected for mutation in MUTATIONS}:
        raise ValueError('Exception proof coverage differs')
    actor_rows=0
    for case,candidate in expected:
        folder=HERE/'saved-fixtures'/case/candidate
        packet_path=folder/'exception-evidence.json';packet=json.loads(packet_path.read_text())
        doc=folder/'authority/synthetic-exception-source.json'
        if packet['source_kind']!='synthetic_cpu' or packet['review_status']!='pending_independent_review' or packet['native_capture_report_sha256']!=sha(folder/'native-capture-report.json') or packet['native_map_readback_sha256']!=sha(folder/'native-map-readback.json'):
            raise ValueError('Exception capture or packet source differs')
        if set(packet['facts'])!=set(FACTS) or any(row!={'value':False,'document_path':'authority/synthetic-exception-source.json','document_sha256':sha(doc),'citation':'synthetic diagnostic only','reviewed':False} for row in packet['facts'].values()):
            raise ValueError('Exception fact or document differs')
        source=json.loads(doc.read_text())
        if source['source_kind']!='synthetic_cpu' or 'Diagnostic' not in source['note']:
            raise ValueError('Exception source provenance differs')
        actual=measure(folder,packet_path)
        if actual!=positives[(case,candidate)] or actual['reported_exception_pattern'] or actual['exception_applies'] is not None or actual['legal_verdict'] is not None or actual['source_hashes']['exception-evidence.json']!=sha(packet_path) or actual['source_hashes']['authority/synthetic-exception-source.json']!=sha(doc):
            raise ValueError('Exception saved measurement differs')
        actor_rows+=actual['frames']
    if actor_rows!=3840:raise ValueError('Exception saved row count differs')
    result={'format':'c422978-heavy-exception-independent-audit-v1',
            'positives':8,'negatives':48,'saved_rows_checked':actor_rows,
            'proof_sha256':sha(HERE/'exception-proof.json'),
            'original_authority_reviewed':False,'delivery_ready':False}
    (HERE/'exception-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':print(json.dumps(audit()))
