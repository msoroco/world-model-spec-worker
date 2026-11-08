"""Bind reported exception facts to saved sources; never make a legal finding."""
import hashlib
import json
from pathlib import Path
from measure_saved import measure as measure_saved

FACTS=('solely_electric','designed_three_wheels','authorized_emergency_vehicle',
       'emergency_operation_at_event','law_enforcement_officer_or_employee',
       'law_enforcement_official_duty_at_event','security_guard_under_definition',
       'security_guard_official_duty_at_event')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(folder, packet_path):
    folder,packet_path=Path(folder),Path(packet_path)
    saved=measure_saved(folder)
    packet=json.loads(packet_path.read_text())
    if (packet.get('format')!='c422978-heavy-exception-evidence-v1' or
            packet.get('law_id')!='NRS-484B-117-1' or
            packet.get('native_capture_report_sha256')!=saved['source_hashes']['native-capture-report.json'] or
            packet.get('native_map_readback_sha256')!=saved['source_hashes']['native-map-readback.json'] or
            packet.get('source_kind')!=saved['source_kind'] or
            packet.get('review_status')!='pending_independent_review' or
            packet.get('legal_verdict') is not None):
        raise ValueError('Exception packet identity, Native binding or status differs')
    facts=packet.get('facts')
    if not isinstance(facts,dict) or set(facts)!=set(FACTS):
        raise ValueError('Exception fact coverage differs')
    values={};docs={}
    for name in FACTS:
        record=facts[name]
        if not isinstance(record,dict) or record.get('value') not in (True,False,None) or type(record.get('value')) not in (bool,type(None)):
            raise ValueError('Exception fact value invalid')
        rel=record.get('document_path')
        if not isinstance(rel,str) or not rel or Path(rel).is_absolute() or '..' in Path(rel).parts or Path(rel).parts[0]!='authority':
            raise ValueError('Exception evidence path invalid')
        path=folder/rel
        if not path.is_file() or record.get('document_sha256')!=sha(path):
            raise ValueError('Exception evidence document hash differs')
        if not isinstance(record.get('citation'),str) or not record['citation']:
            raise ValueError('Exception evidence citation absent')
        if record.get('reviewed') is not False:
            raise ValueError('Exception fact cannot claim independent review')
        values[name]=record['value'];docs[rel]=sha(path)
    electric_three_wheel=(values['solely_electric'] is True and values['designed_three_wheels'] is True)
    role=(values['authorized_emergency_vehicle'] is True and values['emergency_operation_at_event'] is True) or (values['law_enforcement_officer_or_employee'] is True and values['law_enforcement_official_duty_at_event'] is True) or (values['security_guard_under_definition'] is True and values['security_guard_official_duty_at_event'] is True)
    return {'format':'c422978-heavy-exception-measurement-v1',
            'source_kind':saved['source_kind'],'frames':480,
            'reported_facts':values,
            'reported_exception_pattern':bool(electric_three_wheel and role),
            'review_status':'pending_independent_review','exception_applies':None,
            'legal_verdict':None,
            'source_hashes':{**saved['source_hashes'],'exception-evidence.json':sha(packet_path),**docs}}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--attempt',required=True);p.add_argument('--packet',required=True)
    a=p.parse_args();print(json.dumps(measure(a.attempt,a.packet),indent=2))
